"""Assemble a full ``CityRisk`` from already-fetched series (pure apart from the injected
optional ML callback). Used by the live service and by the demo-scenario builder alike, so the
replay runs exactly the same scoring code as production."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from jalrakshak.models import (
    City,
    CityRisk,
    CitySummary,
    GaugeReading,
    HorizonPoint,
    RainPoint,
    RiskScore,
    SourceStatus,
    WardRisk,
)
from jalrakshak.risk.scoring import GaugeRef, RiskInputs, ml_features, score_ward
from jalrakshak.risk.series import (
    HORIZON_H,
    STEP_H,
    discharge_at,
    fmt_ts,
    forward_features,
    gauge_reading,
    now_index,
    parse_ts,
    trailing_features,
)
from jalrakshak.risk.thresholds import level_for

MLFn = Callable[[str, dict[str, float]], float | None]


@dataclass(frozen=True)
class RainSeries:
    time: Sequence[str]
    mm: Sequence[float]


@dataclass(frozen=True)
class DischargeSeries:
    date: Sequence[str]
    m3s: Sequence[float]


def _gauge_ref(reading: GaugeReading, peak: float | None = None) -> GaugeRef:
    g = reading.gauge
    return GaugeRef(
        river=g.river,
        peak_m3s=reading.peak_m3s if peak is None else peak,
        warning_m3s=g.warning_m3s,
        danger_m3s=g.danger_m3s,
        extreme_m3s=g.extreme_m3s,
    )


def _dominant(readings: list[GaugeReading]) -> GaugeReading | None:
    """The gauge with the highest peak/danger ratio drives the river component."""
    if not readings:
        return None
    return max(readings, key=lambda r: r.peak_m3s / max(r.gauge.danger_m3s, 1e-9))


def assess_city(
    city: City,
    ward_rain: Sequence[RainSeries],
    gauge_discharge: Sequence[DischargeSeries],
    now: datetime,
    *,
    sources: list[SourceStatus] | None = None,
    stale: bool = False,
    data_age_minutes: float = 0.0,
    ml: MLFn | None = None,
) -> CityRisk:
    """Score every ward now and over a 3-hourly 72 h horizon; overall = max ward risk."""
    readings = [
        gauge_reading(g, s.date, s.m3s, now)
        for g, s in zip(city.gauges, gauge_discharge, strict=False)
    ]
    dom = _dominant(readings)
    dom_series = (
        gauge_discharge[readings.index(dom)] if dom is not None else DischargeSeries([], [])
    )

    ward_risks: list[WardRisk] = []
    horizon_scores = [0.0] * (HORIZON_H // STEP_H)
    times0 = ward_rain[0].time if ward_rain else []
    for ward, rain in zip(city.wards, ward_rain, strict=True):
        idx = now_index(rain.time, now)
        f = forward_features(rain.mm, idx)
        inputs = RiskInputs(
            rain_24h_mm=f.rain_24h_mm,
            rain_72h_mm=f.rain_72h_mm,
            max_intensity_mmph=f.max_intensity_mmph,
            antecedent_7d_mm=f.antecedent_7d_mm,
            vulnerability=ward.vulnerability,
            gauge=_gauge_ref(dom) if dom is not None else None,
        )
        prob = None
        if ml is not None:
            try:
                prob = ml(city.id, ml_features(inputs))
            except Exception:
                prob = None
        ward_risks.append(WardRisk(ward_id=ward.id, risk=score_ward(inputs, prob)))
        for k in range(len(horizon_scores)):
            t_idx = idx + k * STEP_H
            tf = trailing_features(rain.mm, t_idx, f.antecedent_7d_mm)
            t = now + timedelta(hours=k * STEP_H)
            gref = (
                _gauge_ref(dom, discharge_at(dom_series.date, dom_series.m3s, t))
                if dom is not None
                else None
            )
            s = score_ward(
                RiskInputs(
                    tf.rain_24h_mm,
                    tf.rain_72h_mm,
                    tf.max_intensity_mmph,
                    tf.antecedent_7d_mm,
                    ward.vulnerability,
                    gref,
                )
            ).score
            horizon_scores[k] = max(horizon_scores[k], s)

    overall = _overall(ward_risks)
    base = now.replace(minute=0, second=0, microsecond=0)
    horizon = [
        HorizonPoint(t=fmt_ts(base + timedelta(hours=k * STEP_H)), score=s, level=level_for(s))
        for k, s in enumerate(horizon_scores)
    ]
    rainfall = _city_rain(ward_rain, times0, now)
    return CityRisk(
        city=city,
        generated_at=fmt_ts(now),
        stale=stale,
        data_age_minutes=round(data_age_minutes, 1),
        sources=sources or [],
        overall=overall,
        horizon=horizon,
        rainfall=rainfall,
        gauges=readings,
        wards=ward_risks,
    )


def _overall(wards: list[WardRisk]) -> RiskScore:
    if not wards:
        raise ValueError("city has no wards")
    return max(wards, key=lambda w: w.risk.score).risk.model_copy(deep=True)


def _city_rain(ward_rain: Sequence[RainSeries], times: Sequence[str], now: datetime) -> list[RainPoint]:
    """Hourly ward-mean precipitation for the next 72 h."""
    if not ward_rain or not times:
        return []
    idx = now_index(times, now)
    out: list[RainPoint] = []
    for h in range(HORIZON_H):
        i = idx + h
        if i >= len(times):
            break
        vals = [float(r.mm[i]) for r in ward_rain if i < len(r.mm)]
        out.append(RainPoint(t=times[i], mm=round(sum(vals) / len(vals), 2)))
    return out


def summarise(risk: CityRisk) -> CitySummary:
    """CitySummary for the city list.

    ``peak_time`` is the time of the highest horizon score, or ``None`` when the horizon is
    flat (no meaningful peak)."""
    peak_time = None
    if risk.horizon:
        scores = [p.score for p in risk.horizon]
        if max(scores) - min(scores) >= 0.5:
            peak_time = max(risk.horizon, key=lambda p: p.score).t
    return CitySummary(
        city=risk.city,
        risk=risk.overall,
        peak_time=peak_time,
        stale=risk.stale,
        updated_at=risk.generated_at,
    )


def ward_by_id(risk: CityRisk, ward_id: str) -> RiskScore | None:
    return next((w.risk for w in risk.wards if w.ward_id == ward_id), None)


__all__ = ["DischargeSeries", "RainSeries", "assess_city", "parse_ts", "summarise"]
