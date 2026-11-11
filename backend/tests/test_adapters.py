"""Adapters: cache TTL + stale fallback, OSRM fallback, Open-Meteo parsing, Nominatim (respx)."""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
import respx

from jalrakshak.adapters import nominatim, openmeteo, osrm
from jalrakshak.adapters.cache import FileCache
from jalrakshak.adapters.http import FetchError, get_json

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_cache_fresh_then_stale_fallback(tmp_path: Any) -> None:
    cache = FileCache(tmp_path)
    calls = {"n": 0}

    async def ok() -> Any:
        calls["n"] += 1
        return {"v": 1}

    async def fail() -> Any:
        raise RuntimeError("upstream down")

    r1 = await cache.get_or_fetch("k", 60, ok)
    assert r1.value == {"v": 1} and r1.ok and not r1.stale
    r2 = await cache.get_or_fetch("k", 60, fail)  # fresh hit: fetch not called
    assert r2.ok and calls["n"] == 1
    r3 = await cache.get_or_fetch("k", 0, fail)  # expired + failure -> stale last-known
    assert r3.stale and not r3.ok and r3.value == {"v": 1}
    assert r3.fetched_iso.endswith("Z")
    with pytest.raises(FetchError):
        await cache.get_or_fetch("other", 60, fail)


async def test_cache_corrupt_file_is_ignored(tmp_path: Any) -> None:
    cache = FileCache(tmp_path)
    cache.write("k", 1)
    next(tmp_path.glob("*.json")).write_text("{not json")
    assert cache.read("k") is None


@respx.mock
async def test_get_json_retries_then_raises() -> None:
    route = respx.get("https://x.test/a").mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        await get_json("https://x.test/a", retries=1)
    assert route.call_count == 2
    respx.get("https://x.test/b").mock(return_value=httpx.Response(404))
    with pytest.raises(FetchError):
        await get_json("https://x.test/b", retries=3)


@respx.mock
async def test_osrm_failure_falls_back_to_straight_line() -> None:
    respx.get(url__startswith=osrm.OSRM_URL).mock(side_effect=httpx.ConnectError("down"))
    r = await osrm.route((26.16, 91.77), (26.17, 91.78))
    assert r.method == "straight_line"
    assert r.geometry == [(26.16, 91.77), (26.17, 91.78)]
    assert r.duration_s == pytest.approx(r.distance_m / (4000 / 3600), rel=1e-3)
    assert 1000 < r.distance_m < 2000


@respx.mock
async def test_osrm_bad_code_falls_back() -> None:
    respx.get(url__startswith=osrm.OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute", "routes": []})
    )
    assert (await osrm.route((26.16, 91.77), (26.17, 91.78))).method == "straight_line"


@respx.mock
async def test_osrm_success_uses_walking_speed() -> None:
    respx.get(url__startswith=osrm.OSRM_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 2000.0,
                        "duration": 200.0,
                        "geometry": {"coordinates": [[91.77, 26.16], [91.78, 26.17]]},
                    }
                ],
            },
        )
    )
    walk = await osrm.route((26.16, 91.77), (26.17, 91.78))
    assert walk.method == "osrm" and walk.geometry[0] == (26.16, 91.77)
    assert walk.duration_s == pytest.approx(1800.0)
    drive = await osrm.route((26.16, 91.77), (26.17, 91.78), mode="drive")
    assert drive.duration_s == 200.0


def _forecast_payload(n: int) -> Any:
    row = {
        "hourly": {"time": ["2026-07-01T00:00", "2026-07-01T01:00"], "precipitation": [1.5, None]}
    }
    return [row] * n if n > 1 else row


@respx.mock
async def test_openmeteo_rain_and_discharge_parsing() -> None:
    respx.get(openmeteo.FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_forecast_payload(2))
    )
    res = await openmeteo.fetch_rain([(1.0, 2.0), (3.0, 4.0)])
    assert res.value[0] == {
        "time": ["2026-07-01T00:00:00Z", "2026-07-01T01:00:00Z"],
        "mm": [1.5, 0.0],
    }
    respx.get(openmeteo.FLOOD_URL).mock(
        return_value=httpx.Response(
            200, json={"daily": {"time": ["2026-07-01"], "river_discharge": [12.5]}}
        )
    )
    d = await openmeteo.fetch_discharge([(1.0, 2.0)])
    assert d.value == [{"date": ["2026-07-01"], "m3s": [12.5]}]
    assert (await openmeteo.fetch_discharge([])).value == []


@respx.mock
async def test_openmeteo_location_count_mismatch_is_error() -> None:
    respx.get(openmeteo.FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_forecast_payload(1))
    )
    with pytest.raises(FetchError):
        await openmeteo.fetch_rain([(1.0, 2.0), (3.0, 4.0)])


@respx.mock
async def test_prefetch_splits_into_city_entries() -> None:
    respx.get(openmeteo.FORECAST_URL).mock(
        return_value=httpx.Response(200, json=_forecast_payload(3))
    )
    respx.get(openmeteo.FLOOD_URL).mock(side_effect=httpx.ConnectError("down"))
    await openmeteo.prefetch([[(1.0, 2.0)], [(3.0, 4.0), (5.0, 6.0)]], [[(1.0, 1.0)]])
    respx.get(openmeteo.FORECAST_URL).mock(side_effect=httpx.ConnectError("down"))
    res = await openmeteo.fetch_rain([(3.0, 4.0), (5.0, 6.0)])
    assert res.ok and len(res.value) == 2


@respx.mock
async def test_nominatim_cached_and_india_only() -> None:
    nominatim.MIN_INTERVAL_S = 0.0
    route = respx.get(nominatim.SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json=[{"display_name": "Beltola, Guwahati", "lat": "26.12", "lon": "91.80"}]
        )
    )
    a = await nominatim.geocode("  Beltola  ")
    b = await nominatim.geocode("beltola")
    assert a == b and a[0].lat == 26.12 and route.call_count == 1
    params = route.calls[0].request.url.params
    assert params["countrycodes"] == "in"
    assert "JalRakshak" in route.calls[0].request.headers["user-agent"]
    assert await nominatim.geocode("   ") == []


def test_haversine() -> None:
    assert osrm.haversine_m(0, 0, 0, 1) == pytest.approx(111_195, rel=1e-3)
    assert time.time() > 0
