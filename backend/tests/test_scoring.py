"""Unit tests for the pure risk functions (thresholds, scoring, series, assess, advice)."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from jalrakshak.data.cities import get_city
from jalrakshak.models import RiverGauge
from jalrakshak.risk import scoring as sc
from jalrakshak.risk.advice import advice_for
from jalrakshak.risk.assess import DischargeSeries, RainSeries, assess_city, summarise, ward_by_id
from jalrakshak.risk.series import (
    discharge_at,
    forward_features,
    gauge_reading,
    max_rolling_sum,
    now_index,
    trailing_features,
)
from jalrakshak.risk.thresholds import (
    gauge_status,
    imd_category,
    level_for,
    level_rank,
    max_level,
)

G = sc.GaugeRef("Brahmaputra", 0.0, warning_m3s=30_000, danger_m3s=45_000, extreme_m3s=56_000)


def gauge(peak: float) -> sc.GaugeRef:
    return sc.GaugeRef(G.river, peak, G.warning_m3s, G.danger_m3s, G.extreme_m3s)


def inp(
    r24: float = 0,
    r72: float = 0,
    i: float = 0,
    a: float = 0,
    v: float = 0.5,
    peak: float | None = None,
) -> sc.RiskInputs:
    return sc.RiskInputs(r24, r72, i, a, v, gauge(peak) if peak is not None else None)


# ------------------------------------------------------------------ thresholds


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0, "green"),
        (29.99, "green"),
        (30, "yellow"),
        (54.99, "yellow"),
        (55, "orange"),
        (74.99, "orange"),
        (75, "red"),
        (100, "red"),
    ],
)
def test_level_cutoffs(score: float, level: str) -> None:
    assert level_for(score) == level


def test_level_rank_and_max() -> None:
    assert [level_rank(x) for x in ("green", "yellow", "orange", "red")] == [0, 1, 2, 3]
    assert max_level("yellow", "red", "green") == "red"


@pytest.mark.parametrize(
    ("mm", "cat"),
    [
        (0, "no rain"),
        (0.1, "very light"),
        (2.5, "light"),
        (15.6, "moderate"),
        (64.5, "heavy"),
        (115.6, "very heavy"),
        (204.5, "extremely heavy"),
    ],
)
def test_imd_categories(mm: float, cat: str) -> None:
    assert imd_category(mm) == cat


def test_gauge_status() -> None:
    g = RiverGauge(id="g", river="R", lat=0, lon=0, warning_m3s=10, danger_m3s=20, extreme_m3s=30)
    assert gauge_status(9.9, g) == "normal"
    assert gauge_status(10, g) == "warning"
    assert gauge_status(20, g) == "danger"
    assert gauge_status(30, g) == "extreme"


# ------------------------------------------------------------------ components


def test_piecewise_and_clamp() -> None:
    pts = [(0.0, 0.0), (10.0, 1.0)]
    assert sc.piecewise(-5, pts) == 0.0
    assert sc.piecewise(5, pts) == pytest.approx(0.5)
    assert sc.piecewise(50, pts) == 1.0
    assert sc.clamp(2.0) == 1.0 and sc.clamp(-1.0) == 0.0 and sc.clamp(0.3) == 0.3


def test_rain_component_imd_anchors() -> None:
    assert sc.rain_component(15.6, 0, 0) == 0.0
    assert sc.rain_component(64.5, 0, 0) == pytest.approx(0.35)
    assert sc.rain_component(115.6, 0, 0) == pytest.approx(0.65)
    assert sc.rain_component(204.4, 0, 0) == pytest.approx(1.0)
    assert sc.rain_component(0, 50, 0) == pytest.approx(0.8)  # intensity x0.8
    assert sc.rain_component(0, 10, 0) == 0.0
    assert sc.rain_component(0, 0, 300) == pytest.approx(0.15)
    assert sc.rain_component(500, 100, 900) == 1.0
    assert sc.rain_component(-3, -1, -2) == 0.0


def test_river_and_antecedent_components() -> None:
    assert sc.river_component(0.5) == 0.0
    assert sc.river_component(1.2) == pytest.approx(1.0)
    assert sc.river_component(0.85) == pytest.approx(0.5)
    assert sc.antecedent_component(100) == 0.5
    assert sc.antecedent_component(1000) == 1.0
    assert G.ratio == 0.0
    assert sc.GaugeRef("x", 5, 1, 0, 2).ratio == 0.0


# ------------------------------------------------------------------ score


def test_zero_rain_is_green() -> None:
    s = sc.score_ward(inp(v=0.9))
    assert s.level == "green"
    assert s.factors.components.rain == 0.0
    assert "little or no rain" in s.explanation
    assert s.ml_probability is None


def test_zero_everything_scores_zero() -> None:
    assert sc.score_ward(inp(v=0.0)).score == 0.0


def test_max_everything_scores_100() -> None:
    s = sc.score_ward(inp(300, 500, 80, 400, 1.0, peak=80_000))
    assert s.score == 100.0 and s.level == "red"


def test_rain_only_city_can_reach_red() -> None:
    s = sc.score_ward(inp(250, 400, 60, 150, 0.85))
    assert s.level == "red"
    assert "extremely heavy" in s.explanation


def test_very_heavy_rain_vulnerable_ward_is_orange() -> None:
    assert sc.score_ward(inp(130, 160, 20, 40, 0.85)).level == "orange"


GRID = {
    "r24": [0, 20, 70, 120, 210],
    "i": [0, 15, 40, 60],
    "a": [0, 80, 250],
    "v": [0.0, 0.3, 0.5, 0.8, 1.0],
    "peak": [None, 10_000, 31_000, 46_000, 60_000],
}


def _score(r24: float, i: float, a: float, v: float, peak: float | None) -> float:
    return sc.score_ward(inp(r24, r24 * 1.5, i, a, v, peak)).score


@pytest.mark.parametrize("field", list(GRID))
def test_monotone_in_each_input(field: str) -> None:
    others = {k: vals for k, vals in GRID.items() if k != field}
    for combo in itertools.product(*others.values()):
        kw = dict(zip(others, combo, strict=True))
        values = GRID[field]
        if field == "peak":
            values = [0.0 if x is None else x for x in values]
        prev = -1.0
        for x in values:
            s = _score(**{**kw, field: x})
            assert s >= prev - 1e-9, (field, kw, x)
            prev = s


def test_hard_rules_vulnerable_ward() -> None:
    assert sc.score_ward(inp(v=0.5, peak=45_000)).score >= 75
    assert sc.score_ward(inp(v=0.5, peak=30_000)).score >= 55
    assert sc.score_ward(inp(v=0.5, peak=56_000)).score >= 85
    s = sc.score_ward(inp(v=0.6, peak=46_000))
    assert s.level == "red" and "danger-level rule applied" in s.explanation


def test_hard_rules_less_vulnerable_ward() -> None:
    s = sc.score_ward(inp(v=0.3, peak=46_000))
    assert 30 <= s.score < 75
    assert sc.score_ward(inp(v=0.3, peak=30_000)).score < 55
    assert sc.river_floor(None, 0.9) == (0.0, None)
    assert sc.river_floor(gauge(1000), 0.9) == (0.0, None)


def test_floor_not_reported_when_formula_already_higher() -> None:
    s = sc.score_ward(inp(300, 500, 80, 400, 1.0, peak=31_000))
    assert "rule applied" not in s.explanation


def test_explanation_deterministic_and_mentions_drivers() -> None:
    a = sc.score_ward(inp(120, 200, 30, 120, 0.8, peak=40_000))
    b = sc.score_ward(inp(120, 200, 30, 120, 0.8, peak=40_000))
    assert a.explanation == b.explanation
    for part in ("very heavy rain", "Brahmaputra", "past 7 days", "highly vulnerable"):
        assert part in a.explanation
    assert sc.score_ward(inp(1, v=0.1)).explanation.endswith("less vulnerable ward.")
    assert "moderately" in sc.score_ward(inp(0, i=12, v=0.5)).explanation


def test_ml_probability_passthrough_and_features() -> None:
    i = inp(10, 20, 3, 4, 0.5, peak=22_500)
    assert sc.score_ward(i, 0.42).ml_probability == 0.42
    f = sc.ml_features(i)
    assert set(f) == {
        "rain_24h_mm",
        "rain_72h_mm",
        "max_intensity_mmph",
        "antecedent_7d_mm",
        "discharge_ratio",
        "vulnerability",
    }
    assert f["discharge_ratio"] == pytest.approx(0.5)
    assert sc.ml_features(inp())["discharge_ratio"] == 0.0


# ------------------------------------------------------------------ series


def test_max_rolling_sum() -> None:
    assert max_rolling_sum([1, 2, 3], 24) == 6
    assert max_rolling_sum([0, 5, 5, 0, 1], 2) == 10
    assert max_rolling_sum([], 3) == 0


def test_forward_and_trailing_features() -> None:
    mm = [1.0] * 168 + [0.0] * 10 + [10.0] * 30 + [0.0] * 60
    f = forward_features(mm, 168)
    assert f.antecedent_7d_mm == 168
    assert f.rain_24h_mm == 240 and f.rain_72h_mm == 300 and f.max_intensity_mmph == 10
    t = trailing_features(mm, 168 + 39, 168)
    assert t.rain_24h_mm == 240 and t.max_intensity_mmph == 10 and t.antecedent_7d_mm == 168
    assert forward_features([], 0).rain_24h_mm == 0


def test_now_index_and_discharge_interp() -> None:
    times = ["2026-07-01T00:00:00Z", "2026-07-01T01:00:00Z", "2026-07-01T02:00:00Z"]
    assert now_index(times, datetime(2026, 7, 1, 1, 30, tzinfo=UTC)) == 1
    assert now_index(times, datetime(2026, 8, 1, tzinfo=UTC)) == 2
    assert now_index([], datetime(2026, 8, 1, tzinfo=UTC)) == 0
    dates, vals = ["2026-07-01", "2026-07-02"], [100.0, 200.0]
    assert discharge_at(dates, vals, datetime(2026, 7, 1, tzinfo=UTC)) == 100
    assert discharge_at(dates, vals, datetime(2026, 7, 2, 0, tzinfo=UTC)) == pytest.approx(150)
    assert discharge_at(dates, vals, datetime(2026, 7, 9, tzinfo=UTC)) == 200
    assert discharge_at([], [], datetime(2026, 7, 9, tzinfo=UTC)) == 0


def test_gauge_reading_peak_over_three_days() -> None:
    g = RiverGauge(id="g", river="R", lat=0, lon=0, warning_m3s=10, danger_m3s=20, extreme_m3s=30)
    start = datetime(2026, 7, 1, tzinfo=UTC)
    dates = [(start + timedelta(days=d)).date().isoformat() for d in range(14)]
    vals = [5.0] * 7 + [8.0, 12.0, 21.0, 40.0, 40.0, 40.0, 40.0]
    r = gauge_reading(g, dates, vals, start + timedelta(days=7, hours=6))
    assert r.current_m3s == 8 and r.peak_m3s == 21 and r.peak_date == dates[9]
    assert r.status == "danger" and len(r.series) == 14
    r2 = gauge_reading(g, dates[:3], vals[:3], start + timedelta(days=30))
    assert r2.current_m3s == 5


# ------------------------------------------------------------------ assess


def _flat_city_inputs(
    rain_mm: float, peak: float, now: datetime
) -> tuple[list[RainSeries], list[DischargeSeries]]:
    city = get_city("guwahati")
    assert city is not None
    t0 = now - timedelta(hours=168)
    times = [(t0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(264)]
    rain = [RainSeries(times, [0.0] * 168 + [rain_mm] * 96) for _ in city.wards]
    d0 = now.date() - timedelta(days=7)
    dates = [(d0 + timedelta(days=d)).isoformat() for d in range(14)]
    dis = [DischargeSeries(dates, [peak] * 14) for _ in city.gauges]
    return rain, dis


def test_assess_city_calm_and_flood() -> None:
    now = datetime(2026, 7, 1, 6, tzinfo=UTC)
    city = get_city("guwahati")
    assert city is not None and city.gauges
    rain, dis = _flat_city_inputs(0.0, 5_000, now)
    calm = assess_city(city, rain, dis, now)
    assert calm.overall.level == "green" and len(calm.horizon) == 24 and len(calm.rainfall) == 72
    assert summarise(calm).peak_time is None

    rain, dis = _flat_city_inputs(8.0, city.gauges[0].danger_m3s * 1.05, now)
    calls: list[str] = []

    def ml(cid: str, feats: dict[str, float]) -> float:
        calls.append(cid)
        return 0.9

    flood = assess_city(city, rain, dis, now, ml=ml)
    assert flood.overall.level == "red"
    assert flood.overall.score == max(w.risk.score for w in flood.wards)
    assert flood.gauges[0].status == "danger"
    assert flood.overall.ml_probability == 0.9 and len(calls) == len(city.wards)
    assert summarise(flood).peak_time is not None
    assert ward_by_id(flood, city.wards[0].id) is not None
    assert ward_by_id(flood, "nope") is None
    # horizon is non-decreasing as rain accumulates under constant forcing
    scores = [p.score for p in flood.horizon]
    assert scores == sorted(scores)


def test_assess_ml_failure_is_swallowed() -> None:
    now = datetime(2026, 7, 1, 6, tzinfo=UTC)
    city = get_city("guwahati")
    assert city is not None
    rain, dis = _flat_city_inputs(1.0, 5_000, now)

    def bad(cid: str, feats: dict[str, float]) -> float:
        raise RuntimeError("boom")

    assert assess_city(city, rain, dis, now, ml=bad).overall.ml_probability is None


def test_assess_city_without_gauge() -> None:
    now = datetime(2026, 7, 1, 6, tzinfo=UTC)
    city = get_city("mumbai")
    assert city is not None and not city.gauges
    rain, _ = _flat_city_inputs(12.0, 0, now)
    rain = rain[: len(city.wards)]
    r = assess_city(city, rain, [], now)
    assert r.gauges == [] and r.overall.factors.discharge_ratio == 0.0
    assert r.overall.level in ("orange", "red")


def test_advice_per_level() -> None:
    for lvl in ("green", "yellow", "orange", "red"):
        a = advice_for(lvl)  # type: ignore[arg-type]
        assert a.now and a.prepare and a.avoid
    assert any("112" in x for x in advice_for("red").now)
