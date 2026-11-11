"""API smoke tests: every contract endpoint with RulesProvider and mocked upstreams (respx)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from jalrakshak.adapters import nominatim, openmeteo, osrm
from jalrakshak.api.main import app
from jalrakshak.models import Alert, CityRisk, CitySummary, PointRisk

from .conftest import daily_dates, hourly_times

UPSTREAM = {"down": False}


def _lats(request: httpx.Request) -> list[float]:
    if UPSTREAM["down"]:
        raise httpx.ConnectError("upstream down")
    return [float(x) for x in request.url.params["latitude"].split(",")]


def heavy(lat: float) -> bool:
    """Guwahati (26.1-26.2 N) gets a monsoon burst and a Brahmaputra in spate."""
    return 26.0 < lat < 26.3


def _forecast(request: httpx.Request) -> httpx.Response:
    now = datetime.now(UTC)
    times = [t[:16] for t in hourly_times(now)]
    rows = [
        {
            "hourly": {
                "time": times,
                "precipitation": [1.0] * 168 + [9.0 if heavy(lat) else 0.2] * 96,
            }
        }
        for lat in _lats(request)
    ]
    return httpx.Response(200, json=rows if len(rows) > 1 else rows[0])


def _flood(request: httpx.Request) -> httpx.Response:
    rows = [
        {
            "daily": {
                "time": daily_dates(datetime.now(UTC)),
                "river_discharge": [50_000.0 if heavy(lat) else 100.0] * 14,
            }
        }
        for lat in _lats(request)
    ]
    return httpx.Response(200, json=rows if len(rows) > 1 else rows[0])


@pytest.fixture
def client() -> Iterator[TestClient]:
    nominatim.MIN_INTERVAL_S = 0.0
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as m:
        m.get(openmeteo.FORECAST_URL).mock(side_effect=_forecast)
        m.get(openmeteo.FLOOD_URL).mock(side_effect=_flood)
        m.get(url__startswith=osrm.OSRM_URL).mock(side_effect=httpx.ConnectError("osrm down"))
        m.get(nominatim.SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "display_name": "Pandu, Guwahati, Assam, India",
                        "lat": "26.172",
                        "lon": "91.68",
                    }
                ],
            )
        )
        m.route(host="127.0.0.1").pass_through()
        with TestClient(app) as c:
            yield c


def test_health(client: TestClient) -> None:
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["llm"] == {
        "provider": "rules",
        "model": "deterministic",
        "available": True,
    }
    assert r["demo"] is False


def test_cities_and_risk(client: TestClient) -> None:
    rows = [CitySummary.model_validate(x) for x in client.get("/api/cities").json()]
    assert len(rows) == 12
    by = {r.city.id: r for r in rows}
    assert by["guwahati"].risk.level == "red" and by["kolkata"].risk.level in ("green", "yellow")
    risk = CityRisk.model_validate(client.get("/api/cities/guwahati/risk").json())
    assert (
        len(risk.horizon) == 24 and len(risk.rainfall) == 72 and risk.gauges[0].status == "danger"
    )
    assert risk.sources and all(s.ok for s in risk.sources) and not risk.stale
    assert len(risk.wards) == len(risk.city.wards)
    assert client.get("/api/cities/atlantis/risk").status_code == 404


def test_facilities_point_geocode_evacuation(client: TestClient) -> None:
    fac = client.get("/api/cities/guwahati/facilities").json()
    assert 8 <= len(fac) <= 12 and all(f["phone"].startswith("+91-00000-") for f in fac)
    assert client.get("/api/cities/atlantis/facilities").status_code == 404
    pr = PointRisk.model_validate(
        client.get("/api/risk/point", params={"lat": 26.165, "lon": 91.771}).json()
    )
    assert pr.city.id == "guwahati" and pr.ward.name == "Anil Nagar"
    assert pr.evacuation.route.method == "straight_line" and pr.advice.now
    assert any(c.number == "112" for c in pr.emergency)
    assert client.get("/api/risk/point", params={"lat": 51.5, "lon": 0}).status_code == 422
    geo = client.get("/api/geocode", params={"q": "pandu, guwahati"}).json()
    assert geo[0]["lat"] == 26.172
    plan = client.post("/api/evacuation/plan", json={"lat": 26.17, "lon": 91.68}).json()
    assert plan["route"]["method"] == "straight_line" and len(plan["alternatives"]) <= 2
    assert plan["route"]["geometry"][0] == [26.17, 91.68]
    assert (
        client.post(
            "/api/evacuation/plan", json={"lat": 26.17, "lon": 91.68, "city_id": "x"}
        ).status_code
        == 404
    )


def test_agents_alerts_gate_and_pdf(client: TestClient) -> None:
    run = client.post("/api/agents/run", json={"city_id": "guwahati"}).json()
    assert run["decision"]["should_alert"] and run["llm"]["provider"] == "rules"
    assert run["trigger"] == "manual" and run["alert_id"]
    assert client.post("/api/agents/run", json={"city_id": "nowhere"}).status_code == 404
    assert client.get(f"/api/agents/runs/{run['id']}").json()["id"] == run["id"]
    assert client.get("/api/agents/runs/none").status_code == 404
    assert (
        client.get("/api/agents/runs", params={"city_id": "guwahati"}).json()[0]["id"] == run["id"]
    )
    tl = client.get("/api/timeline", params={"limit": 5}).json()
    assert len(tl) == 5 and tl[0]["run_id"] == run["id"]

    pending = [
        Alert.model_validate(a)
        for a in client.get("/api/alerts", params={"status": "pending_approval"}).json()
    ]
    alert = next(a for a in pending if a.id == run["alert_id"])
    assert len(alert.versions) == 5 and all(g.passed for g in alert.guards)

    versions: list[dict[str, Any]] = [v.model_dump() for v in alert.versions]
    versions[0]["sms"] = "RED ALERT Guwahati: 12345 boats coming. Call 112"
    edited = client.put(
        f"/api/alerts/{alert.id}", json={"versions": versions, "reviewer": "Officer Bora"}
    ).json()
    assert edited["edited"] and not all(g["passed"] for g in edited["guards"])
    r = client.post(f"/api/alerts/{alert.id}/approve", json={"reviewer": "Officer Bora"})
    assert r.status_code == 409 and "numbers_verified" in r.json()["detail"]
    client.put(
        f"/api/alerts/{alert.id}",
        json={"versions": [v.model_dump() for v in alert.versions], "reviewer": "Officer Bora"},
    )
    assert client.post(f"/api/alerts/{alert.id}/approve", json={"reviewer": ""}).status_code == 422
    sent = client.post(f"/api/alerts/{alert.id}/approve", json={"reviewer": "Officer Bora"}).json()
    assert (
        sent["status"] == "sent"
        and sent["dispatch_log"]
        and sent["dispatch_log"][0]["simulated"] is True
    )
    assert (
        client.post(
            f"/api/alerts/{alert.id}/reject", json={"reviewer": "X Y", "reason": "r"}
        ).status_code
        == 409
    )

    run2 = client.post("/api/agents/run", json={"city_id": "guwahati", "trigger": "demo"}).json()
    rej = client.post(
        f"/api/alerts/{run2['alert_id']}/reject", json={"reviewer": "Officer Bora", "reason": "dup"}
    ).json()
    assert rej["status"] == "rejected"
    assert {a["status"] for a in client.get("/api/alerts").json()} == {"sent", "rejected"}

    pdf = client.get(f"/api/sitrep/{run['id']}.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert client.get("/api/sitrep/none.pdf").status_code == 404
    assert client.get("/api/nope").status_code == 404


def test_stale_fallback_when_upstream_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jalrakshak.api.main import state

    assert client.get("/api/cities/patna/risk").json()["stale"] is False
    state.service.clear()
    monkeypatch.setattr(openmeteo, "RAIN_TTL_S", 0)
    monkeypatch.setattr(openmeteo, "DISCHARGE_TTL_S", 0)
    monkeypatch.setitem(UPSTREAM, "down", True)
    risk = client.get("/api/cities/patna/risk").json()
    assert risk["stale"] is True and not any(s["ok"] for s in risk["sources"])
    assert risk["gauges"]  # last-known values still used
