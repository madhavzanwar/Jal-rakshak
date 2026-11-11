"""Build ``frontend/public/demo/scenario.json`` -- the offline demo replay (DemoScenario).

24 frames x 3 h covering a 72 h flood build-up starting ``T0``.

* Guwahati and Dibrugarh (and, mildly, Patna) get a SYNTHETIC forcing inspired by Assam
  monsoon floods: a week of monsoon rain (antecedent), then rain building to ~200-250 mm/24 h
  and the Brahmaputra rising from ~P80 through warning and danger to above its extreme
  threshold (Dibrugarh, upstream, leads Guwahati by ~12 h). The forecast seen at each frame
  is "truth" blended towards the current state with lead-time-dependent skill, so risk rises
  gradually as the event approaches, as it would with real forecasts.
* The other nine cities use one real live Open-Meteo snapshot (rain + GloFAS) captured at
  build time and re-anchored to ``T0`` (calm synthetic series if offline).
* Every frame is scored with the REAL scoring code (``assess_city``). Where Guwahati or
  Dibrugarh (or Patna) newly reach orange or red, the REAL agent pipeline runs (Ollama if
  reachable, else rules) and its AgentRuns and Alerts are recorded, timestamps re-anchored to
  the frame time.

Usage: ``python scripts/build_demo_scenario.py [--provider auto|ollama|rules] [--no-agents]``
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jalrakshak.adapters import nominatim, openmeteo  # noqa: E402
from jalrakshak.adapters.http import FetchError  # noqa: E402
from jalrakshak.agents.llm import get_provider  # noqa: E402
from jalrakshak.agents.pipeline import run_pipeline  # noqa: E402
from jalrakshak.data.cities import all_cities  # noqa: E402
from jalrakshak.data.facilities import all_facilities  # noqa: E402
from jalrakshak.models import (  # noqa: E402
    AgentRun,
    Alert,
    City,
    CityRisk,
    DemoFrame,
    DemoScenario,
    FrameRun,
    GeocodeResult,
    RecordedWith,
    RiverGauge,
    SourceStatus,
)
from jalrakshak.risk.assess import DischargeSeries, RainSeries, assess_city, summarise  # noqa: E402
from jalrakshak.risk.series import fmt_ts, parse_ts  # noqa: E402
from jalrakshak.risk.thresholds import level_rank  # noqa: E402
from jalrakshak.service import load_ml  # noqa: E402

OUT = ROOT.parent / "frontend" / "public" / "demo" / "scenario.json"
T0 = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
FRAMES = 24
STEP_H = 3
PAST_H = 168
FUTURE_H = 72 + FRAMES * STEP_H + 24  # forward window of the last frame plus margin
DAYS_BEFORE, DAYS_AFTER = 7, 14
SYNTH: dict[str, dict[str, Any]] = {
    # daily rain totals (mm) for days 0..6 after T0; antecedent mm/day; river level index per
    # day (0=P80, 1=warning, 2=danger, 3=extreme); time shift in days (positive = earlier)
    "guwahati": {
        "rain": [12, 35, 90, 210, 250, 130, 40],
        "ante": 13,
        "river": [-0.8, -0.2, 0.9, 2.2, 3.3, 3.5, 3.1, 2.6],
        "shift": 0.0,
    },
    "dibrugarh": {
        "rain": [15, 45, 120, 230, 220, 90, 30],
        "ante": 15,
        "river": [-0.8, -0.2, 0.9, 2.2, 3.3, 3.5, 3.1, 2.6],
        "shift": 0.3,
    },
    "patna": {
        "rain": [10, 25, 55, 70, 45, 20, 10],
        "ante": 9,
        "river": [0.0, 0.3, 0.65, 0.95, 1.15, 1.2, 1.1, 1.0],
        "shift": 0.0,
    },
}
GEOCODE_QUERIES = {
    "guwahati": ("Guwahati, Kamrup Metropolitan, Assam, India", "guwahati", None),
    "pandu, guwahati": ("Pandu, Guwahati, Kamrup Metropolitan, Assam, India", "guwahati", "Pandu"),
    "pandu": ("Pandu, Guwahati, Kamrup Metropolitan, Assam, India", "guwahati", "Pandu"),
    "beltola": ("Beltola, Guwahati, Kamrup Metropolitan, Assam, India", "guwahati", "Beltola"),
    "beltola, guwahati": (
        "Beltola, Guwahati, Kamrup Metropolitan, Assam, India",
        "guwahati",
        "Beltola",
    ),
    "anil nagar, guwahati": (
        "Anil Nagar, Guwahati, Kamrup Metropolitan, Assam, India",
        "guwahati",
        "Anil Nagar",
    ),
    "zoo road, guwahati": (
        "Zoo Road, Guwahati, Kamrup Metropolitan, Assam, India",
        "guwahati",
        "Zoo Road",
    ),
    "dibrugarh": ("Dibrugarh, Assam, India", "dibrugarh", None),
    "graham bazar, dibrugarh": (
        "Graham Bazar, Dibrugarh, Assam, India",
        "dibrugarh",
        "Graham Bazar",
    ),
    "patna": ("Patna, Bihar, India", "patna", None),
    "kankarbagh, patna": ("Kankarbagh, Patna, Bihar, India", "patna", "Kankarbagh"),
    "mumbai": ("Mumbai, Maharashtra, India", "mumbai", None),
    "chennai": ("Chennai, Tamil Nadu, India", "chennai", None),
    "kolkata": ("Kolkata, West Bengal, India", "kolkata", None),
}


# ---------------------------------------------------------------- synthetic forcing


def _hour_times() -> list[datetime]:
    start = T0 - timedelta(hours=PAST_H)
    return [start + timedelta(hours=h) for h in range(PAST_H + FUTURE_H)]


def _diurnal(h_utc: int) -> float:
    """Monsoon convective weighting: wetter in the late afternoon / night (IST)."""
    ist = (h_utc + 5.5) % 24
    return 1.0 + 0.6 * math.cos(2 * math.pi * (ist - 20) / 24)


def truth_rain(cfg: dict[str, Any], ward_idx: int, seed: str) -> list[float]:
    """True hourly rain (mm) on the scenario timeline for one ward."""
    rng = random.Random(f"{seed}-{ward_idx}")
    out: list[float] = []
    ward_factor = 0.85 + 0.3 * rng.random()
    for t in _hour_times():
        day = (t - T0).total_seconds() / 86400 + cfg["shift"]
        if day < 0:
            daily = cfg["ante"] * (0.6 + 0.8 * rng.random())
        else:
            i = min(int(day), len(cfg["rain"]) - 1)
            j = min(i + 1, len(cfg["rain"]) - 1)
            frac = day - int(day)
            daily = cfg["rain"][i] * (1 - frac) + cfg["rain"][j] * frac
        burst = 0.7 + 0.6 * rng.random()
        out.append(max(0.0, daily / 24 * _diurnal(t.hour) * burst * ward_factor))
    return out


def rain_skill(lead_h: float) -> float:
    """Fraction of the true future rain present in the forecast at a given lead time."""
    if lead_h <= 3:
        return 1.0
    if lead_h <= 48:
        return 1.0 - 0.7 * (lead_h - 3) / 45
    return max(0.2, 0.3 - 0.1 * (lead_h - 48) / 24)


def forecast_view(truth: list[float], now_idx: int) -> list[float]:
    """Observed rain up to now, skill-damped forecast afterwards."""
    return [v if i < now_idx else v * rain_skill(i - now_idx) for i, v in enumerate(truth)]


def level_to_m3s(level: float, g: RiverGauge, p80: float) -> float:
    """Map a level index (0=P80, 1=warning, 2=danger, 3=extreme) to discharge."""
    anchors = [p80, g.warning_m3s, g.danger_m3s, g.extreme_m3s]
    if level <= 0:
        return p80 * (1 + 0.35 * level)
    if level >= 3:
        return g.extreme_m3s * (1 + 0.06 * (level - 3))
    i = int(level)
    return anchors[i] + (anchors[i + 1] - anchors[i]) * (level - i)


def truth_level(cfg: dict[str, Any], day: float) -> float:
    d = day + cfg["shift"]
    river: list[float] = cfg["river"]
    if d < 0:
        return max(river[0] - 0.4, river[0] + 0.06 * d)
    i = min(int(d), len(river) - 1)
    j = min(i + 1, len(river) - 1)
    return river[i] + (river[j] - river[i]) * (d - int(d))


def river_skill(lead_days: float) -> float:
    return 1.0 if lead_days <= 0.5 else max(0.6, 1.0 - 0.15 * (lead_days - 0.5))


def discharge_view(
    cfg: dict[str, Any], g: RiverGauge, p80: float, now: datetime
) -> DischargeSeries:
    """Daily discharge as forecast at ``now`` (past days observed)."""
    now_day = (now - T0).total_seconds() / 86400
    cur = truth_level(cfg, now_day)
    dates, vals = [], []
    for k in range(-DAYS_BEFORE, DAYS_AFTER):
        day = (T0 + timedelta(days=k)).date()
        mid = k + 0.5
        lead = mid - now_day
        lvl = truth_level(cfg, mid)
        if lead > 0:
            lvl = cur + (lvl - cur) * river_skill(lead)
        dates.append(day.isoformat())
        vals.append(round(level_to_m3s(lvl, g, p80), 1))
    return DischargeSeries(dates, vals)


# ---------------------------------------------------------------- live snapshot


async def live_snapshot(city: City) -> tuple[list[list[float]], list[DischargeSeries], bool]:
    """Real Open-Meteo rain + discharge re-anchored so live 'now' == T0."""
    n = len(_hour_times())
    try:
        rain = await openmeteo.fetch_rain([(w.lat, w.lon) for w in city.wards])
        dis = await openmeteo.fetch_discharge([(g.lat, g.lon) for g in city.gauges])
    except FetchError:
        calm = [[0.0] * n for _ in city.wards]
        dis_calm = [
            DischargeSeries(
                [
                    (T0 + timedelta(days=k)).date().isoformat()
                    for k in range(-DAYS_BEFORE, DAYS_AFTER)
                ],
                [g.warning_m3s * 0.3] * (DAYS_BEFORE + DAYS_AFTER),
            )
            for g in city.gauges
        ]
        return calm, dis_calm, False
    live_now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    series: list[list[float]] = []
    for row in rain.value:
        t_first = parse_ts(row["time"][0])
        offset = int((live_now - t_first).total_seconds() // 3600)  # index of live "now"
        vals = row["mm"]
        series.append(
            [
                float(vals[i]) if 0 <= (i := offset - PAST_H + h) < len(vals) else 0.0
                for h in range(n)
            ]
        )
    day_shift = (live_now.date() - T0.date()).days
    dseries = []
    for row in dis.value:
        dmap = {
            (datetime.fromisoformat(d).date() - timedelta(days=day_shift)).isoformat(): v
            for d, v in zip(row["date"], row["m3s"], strict=False)
        }
        dates = [
            (T0 + timedelta(days=k)).date().isoformat() for k in range(-DAYS_BEFORE, DAYS_AFTER)
        ]
        last = row["m3s"][-1] if row["m3s"] else 0.0
        dseries.append(DischargeSeries(dates, [round(dmap.get(d, last), 1) for d in dates]))
    return series, dseries, True


# ---------------------------------------------------------------- helpers


def _shift_ts(ts: str | None, delta: timedelta) -> str | None:
    if ts is None:
        return None
    return fmt_ts(parse_ts(ts) + delta)


def reanchor(
    run: AgentRun, alert: Alert | None, frame_t: datetime
) -> tuple[AgentRun, Alert | None]:
    """Shift run/alert timestamps so the run appears to start at the frame time."""
    delta = frame_t + timedelta(minutes=2) - parse_ts(run.started_at)
    steps = [s.model_copy(update={"ts": _shift_ts(s.ts, delta)}) for s in run.steps]
    sitrep = (
        run.sitrep.model_copy(update={"generated_at": _shift_ts(run.sitrep.generated_at, delta)})
        if run.sitrep
        else None
    )
    run = run.model_copy(
        update={
            "started_at": _shift_ts(run.started_at, delta),
            "finished_at": _shift_ts(run.finished_at, delta),
            "steps": steps,
            "sitrep": sitrep,
        }
    )
    if alert is not None:
        alert = alert.model_copy(update={"created_at": _shift_ts(alert.created_at, delta)})
    return run, alert


def _round(obj: Any, key: str = "") -> Any:
    if isinstance(obj, float):
        if key in ("lat", "lon"):
            return round(obj, 4)
        if (
            key in ("score", "ml_probability", "vulnerability")
            or key.startswith("rain")
            or key == "mm"
        ):
            return round(obj, 2)
        return round(obj, 2) if abs(obj) < 1000 else round(obj, 1)
    if isinstance(obj, list):
        if key == "geometry":
            return [[round(c, 5) for c in pt] for pt in obj]
        return [_round(v, key) for v in obj]
    if isinstance(obj, dict):
        return {k: _round(v, k) for k, v in obj.items()}
    return obj


def caption(frame: int, t: datetime, risks: dict[str, CityRisk], events: list[str]) -> str:
    ist = t + timedelta(hours=5, minutes=30)
    parts = [f"Day {frame * STEP_H // 24 + 1}, {ist:%d %b %H:%M} IST."]
    for cid in ("dibrugarh", "guwahati"):
        r = risks[cid]
        g = r.gauges[0] if r.gauges else None
        river = (
            f", Brahmaputra {round(100 * g.peak_m3s / g.gauge.danger_m3s)}% of danger" if g else ""
        )
        parts.append(f"{r.city.name} {r.overall.level.upper()} ({r.overall.score:.0f}){river}.")
    p = risks["patna"]
    parts.append(f"Patna {p.overall.level} ({p.overall.score:.0f}).")
    return " ".join(parts + events)


async def canned_geocode() -> dict[str, list[GeocodeResult]]:
    """Canned answers for demo searches: live Nominatim (cached) restricted to within 25 km of
    the intended city, else the ward/city centroid."""
    from jalrakshak.adapters.osrm import haversine_m

    cities = all_cities()
    out: dict[str, list[GeocodeResult]] = {}
    for q, (name, cid, ward) in GEOCODE_QUERIES.items():
        c = cities[cid]
        search = f"{ward}, {c.name}" if ward else f"{c.name}, {c.state}"
        try:
            res = await nominatim.geocode(search, limit=5)
        except FetchError:
            res = []
        res = [r for r in res if haversine_m(r.lat, r.lon, c.lat, c.lon) < 25_000]
        if not res:
            w = next((x for x in c.wards if x.name == ward), None)
            res = [
                GeocodeResult(
                    display_name=name, lat=w.lat if w else c.lat, lon=w.lon if w else c.lon
                )
            ]
        out[q] = res[:3]
    return out


# ---------------------------------------------------------------- main


async def build(provider_choice: str, agents: bool) -> DemoScenario:
    cities = all_cities()
    ml = load_ml()
    gauges_meta = json.loads((ROOT / "jalrakshak" / "data" / "gauges.json").read_text())[
        "diagnostics"
    ]
    provider = await get_provider(provider_choice)
    print(f"provider: {provider.name} / {provider.model}; ml: {ml is not None}")

    # per-city base data
    truth: dict[str, list[list[float]]] = {}
    live_dis: dict[str, list[DischargeSeries]] = {}
    live_ok: dict[str, bool] = {}
    captured = fmt_ts(datetime.now(UTC))
    for cid, city in cities.items():
        if cid in SYNTH:
            truth[cid] = [truth_rain(SYNTH[cid], i, cid) for i in range(len(city.wards))]
        else:
            truth[cid], live_dis[cid], live_ok[cid] = await live_snapshot(city)
    times = [fmt_ts(t) for t in _hour_times()]

    frames: list[DemoFrame] = []
    runs: list[FrameRun] = []
    alerts: list[Alert] = []
    prev_level: dict[str, int] = {}
    for k in range(FRAMES):
        now = T0 + timedelta(hours=k * STEP_H)
        now_idx = PAST_H + k * STEP_H
        risks: dict[str, CityRisk] = {}
        for cid, city in cities.items():
            if cid in SYNTH:
                rain = [RainSeries(times, forecast_view(t, now_idx)) for t in truth[cid]]
                dis = [
                    discharge_view(SYNTH[cid], g, gauges_meta[cid]["p80_m3s"], now)
                    for g in city.gauges
                ]
                sources = [
                    SourceStatus(
                        name="Synthetic scenario forcing (Assam-monsoon-inspired replay)",
                        url="",
                        ok=True,
                        fetched_at=None,
                    )
                ]
            else:
                rain = [RainSeries(times, t) for t in truth[cid]]
                dis = live_dis[cid]
                sources = [
                    SourceStatus(
                        name="Open-Meteo Forecast (live snapshot, re-anchored)",
                        url=openmeteo.FORECAST_URL,
                        ok=live_ok[cid],
                        fetched_at=captured if live_ok[cid] else None,
                    ),
                ]
                if city.gauges:
                    sources.append(
                        SourceStatus(
                            name="Open-Meteo Flood API (GloFAS, live snapshot)",
                            url=openmeteo.FLOOD_URL,
                            ok=live_ok[cid],
                            fetched_at=captured if live_ok[cid] else None,
                        )
                    )
            risks[cid] = assess_city(city, rain, dis, now, sources=sources, ml=ml)
        events: list[str] = []
        for cid in ("dibrugarh", "guwahati", "patna"):
            lvl = level_rank(risks[cid].overall.level)
            if lvl >= 2 and lvl > prev_level.get(cid, 0):
                name = cities[cid].name
                events.append(
                    f"{name} reaches {risks[cid].overall.level.upper()}: agents drafting an alert for officer approval."
                )
                if agents:
                    print(
                        f"frame {k}: running agents for {cid} ({risks[cid].overall.level})",
                        flush=True,
                    )
                    t0 = datetime.now(UTC)
                    run, alert = await run_pipeline(risks[cid], trigger="demo", provider=provider)
                    print(
                        f"  done in {(datetime.now(UTC) - t0).total_seconds():.0f}s; alert={alert is not None}",
                        flush=True,
                    )
                    run, alert = reanchor(run, alert, now)
                    runs.append(FrameRun(frame=k, run=run))
                    if alert is not None:
                        alerts.append(alert)
            prev_level[cid] = max(prev_level.get(cid, 0), lvl)
        frames.append(
            DemoFrame(
                index=k,
                t=fmt_ts(now),
                caption=caption(k, now, risks, events),
                cities=[summarise(r) for r in risks.values()],
                details=risks,
            )
        )
        print(
            f"frame {k:2d} "
            + " ".join(
                f"{c[:4]}={risks[c].overall.score:.0f}"
                for c in ("dibrugarh", "guwahati", "patna", "mumbai")
            )
        )

    return DemoScenario(
        title="Assam 2026 monsoon flood replay (synthetic)",
        description=(
            "Synthetic replay inspired by Assam monsoon floods - not real observations. A 72-hour "
            "build-up in which rain over Guwahati and Dibrugarh reaches 200-250 mm/24 h and the "
            "Brahmaputra rises from about its 80th percentile past GloFAS danger and extreme "
            "thresholds; Patna sees a milder Ganga rise. Other cities show a real Open-Meteo "
            f"snapshot captured {captured[:10]}. Every frame is scored by the real JalRakshak risk "
            "engine, and the agent runs and alerts were produced by the real agent pipeline."
        ),
        recorded_with=RecordedWith(
            provider=provider.name, model=provider.model, recorded_at=captured
        ),
        frames=frames,
        facilities=all_facilities(),
        agent_runs=runs,
        alerts=alerts,
        geocode=await canned_geocode(),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="auto")
    ap.add_argument("--no-agents", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    scenario = asyncio.run(build(args.provider, not args.no_agents))
    data = _round(scenario.model_dump(mode="json"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {len(scenario.agent_runs)} agent runs, "
        f"{len(scenario.alerts)} alerts, provider {scenario.recorded_with.provider})"
    )


if __name__ == "__main__":
    main()
