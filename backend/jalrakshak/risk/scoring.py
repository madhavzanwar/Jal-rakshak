"""Transparent, monotone flood-risk score (pure functions, no IO).

Formula (also in ``backend/RISK_FORMULA.md``)::

    R  rain       = min(1, max(r24, 0.8*ri) + 0.15*r72)
         r24 = piecewise(rain_24h; 15.6->0, 64.5->0.35, 115.6->0.65, 204.4->1)   (IMD anchors)
         ri  = piecewise(max_intensity; 10 mm/h->0, 50 mm/h->1)
         r72 = piecewise(rain_72h; 64.5->0, 300->1)
    D  river      = clamp((peak / danger - 0.5) / 0.7)        (0 when the city has no gauge)
    A  antecedent = clamp(antecedent_7d / 200)
    V  vulnerability (ward, 0..1)
    H  hazard     = 1 - (1 - R)(1 - D)                        (either source alone can be severe)
    score = 100 * (0.75 H + 0.10 A + 0.15 V) * (0.6 + 0.4 V)

Hard floors (river danger-level rules), applied as ``max(score, floor)``:
    peak >= danger  -> score >= 30 for every ward
    peak >= warning and V >= 0.5 -> score >= 55
    peak >= danger  and V >= 0.5 -> score >= 75
    peak >= extreme and V >= 0.5 -> score >= 85

Every term is non-decreasing in every input and the floors are non-decreasing step functions,
so the final score is monotone non-decreasing in rain, discharge, antecedent rain and
vulnerability.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from jalrakshak.models import RiskComponents, RiskFactors, RiskScore
from jalrakshak.risk.thresholds import imd_category, level_for

R24_POINTS: list[tuple[float, float]] = [(15.6, 0.0), (64.5, 0.35), (115.6, 0.65), (204.4, 1.0)]
INTENSITY_POINTS: list[tuple[float, float]] = [(10.0, 0.0), (50.0, 1.0)]
R72_POINTS: list[tuple[float, float]] = [(64.5, 0.0), (300.0, 1.0)]
INTENSITY_WEIGHT = 0.8
R72_WEIGHT = 0.15
ANTECEDENT_FULL_MM = 200.0
W_HAZARD, W_ANTECEDENT, W_VULN = 0.75, 0.10, 0.15
VULN_FLOOR_MIN = 0.5


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def piecewise(x: float, points: Sequence[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation through ``points`` (sorted by x), flat outside."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


@dataclass(frozen=True)
class GaugeRef:
    """River thresholds and forecast peak used for the river component."""

    river: str
    peak_m3s: float
    warning_m3s: float
    danger_m3s: float
    extreme_m3s: float

    @property
    def ratio(self) -> float:
        return self.peak_m3s / self.danger_m3s if self.danger_m3s > 0 else 0.0


@dataclass(frozen=True)
class RiskInputs:
    rain_24h_mm: float
    rain_72h_mm: float
    max_intensity_mmph: float
    antecedent_7d_mm: float
    vulnerability: float
    gauge: GaugeRef | None = None


def rain_component(rain_24h_mm: float, max_intensity_mmph: float, rain_72h_mm: float) -> float:
    """R in 0..1: IMD-anchored 24 h total or short-burst intensity, plus a 72 h total term."""
    r24 = piecewise(max(rain_24h_mm, 0.0), R24_POINTS)
    ri = piecewise(max(max_intensity_mmph, 0.0), INTENSITY_POINTS)
    r72 = piecewise(max(rain_72h_mm, 0.0), R72_POINTS)
    return clamp(max(r24, INTENSITY_WEIGHT * ri) + R72_WEIGHT * r72)


def river_component(discharge_ratio: float) -> float:
    """D in 0..1: 0 at half the danger discharge, 1 at 1.2x danger."""
    return clamp((discharge_ratio - 0.5) / 0.7)


def antecedent_component(antecedent_7d_mm: float) -> float:
    """A in 0..1: soil/drainage saturation proxy, saturating at 200 mm in 7 days."""
    return clamp(antecedent_7d_mm / ANTECEDENT_FULL_MM)


def river_floor(gauge: GaugeRef | None, vulnerability: float) -> tuple[float, str | None]:
    """Minimum score imposed by river danger-level rules, with the rule's description."""
    if gauge is None:
        return 0.0, None
    p = gauge.peak_m3s
    if vulnerability >= VULN_FLOOR_MIN:
        if p >= gauge.extreme_m3s:
            return 85.0, "extreme"
        if p >= gauge.danger_m3s:
            return 75.0, "danger"
        if p >= gauge.warning_m3s:
            return 55.0, "warning"
    elif p >= gauge.danger_m3s:
        return 30.0, "danger"
    return 0.0, None


def raw_score(r: float, d: float, a: float, v: float) -> float:
    """Weighted score before floors (0..100)."""
    hazard = 1.0 - (1.0 - r) * (1.0 - d)
    return 100.0 * (W_HAZARD * hazard + W_ANTECEDENT * a + W_VULN * v) * (0.6 + 0.4 * v)


def _vuln_word(v: float) -> str:
    return "highly" if v >= 0.7 else "moderately" if v >= 0.4 else "less"


def explain(
    score: float, inputs: RiskInputs, r: float, d: float, a: float, rule: str | None
) -> str:
    """Deterministic one-sentence explanation of the dominant drivers."""
    level = level_for(score)
    drivers: list[str] = []
    cat = imd_category(inputs.rain_24h_mm)
    if inputs.rain_24h_mm >= 2.5 or inputs.max_intensity_mmph >= 10:
        part = f"{cat} rain forecast ({inputs.rain_24h_mm:.0f} mm in 24 h"
        if inputs.max_intensity_mmph >= 10:
            part += f", bursts up to {inputs.max_intensity_mmph:.0f} mm/h"
        drivers.append(part + ")")
    if inputs.gauge is not None and inputs.gauge.ratio >= 0.5:
        drivers.append(
            f"{inputs.gauge.river} forecast to reach {inputs.gauge.ratio * 100:.0f}% of "
            "its danger discharge"
        )
    if a >= 0.4:
        drivers.append(f"wet ground after {inputs.antecedent_7d_mm:.0f} mm in the past 7 days")
    if not drivers:
        drivers.append("little or no rain forecast and rivers below warning levels")
    text = (
        " and ".join(drivers)
        if len(drivers) <= 2
        else ", ".join(drivers[:-1]) + (f" and {drivers[-1]}")
    )
    sentence = (
        f"{level.capitalize()} risk ({score:.0f}/100): {text}, in a "
        f"{_vuln_word(inputs.vulnerability)} vulnerable ward"
    )
    if rule is not None:
        sentence += f"; river {rule}-level rule applied"
    return sentence + "."


def score_ward(inputs: RiskInputs, ml_probability: float | None = None) -> RiskScore:
    """Compute the full RiskScore for one ward (pure, deterministic)."""
    v = clamp(inputs.vulnerability)
    r = rain_component(inputs.rain_24h_mm, inputs.max_intensity_mmph, inputs.rain_72h_mm)
    ratio = inputs.gauge.ratio if inputs.gauge is not None else 0.0
    d = river_component(ratio)
    a = antecedent_component(inputs.antecedent_7d_mm)
    base = raw_score(r, d, a, v)
    floor, rule = river_floor(inputs.gauge, v)
    applied = rule if floor > base else None
    score = round(max(base, floor), 1)
    factors = RiskFactors(
        rain_24h_mm=round(inputs.rain_24h_mm, 1),
        rain_72h_mm=round(inputs.rain_72h_mm, 1),
        max_intensity_mmph=round(inputs.max_intensity_mmph, 1),
        antecedent_7d_mm=round(inputs.antecedent_7d_mm, 1),
        discharge_ratio=round(ratio, 3),
        vulnerability=round(v, 2),
        components=RiskComponents(
            rain=round(r, 3), river=round(d, 3), antecedent=round(a, 3), vulnerability=round(v, 3)
        ),
    )
    return RiskScore(
        score=score,
        level=level_for(score),
        factors=factors,
        explanation=explain(score, inputs, r, d, a, applied),
        ml_probability=ml_probability,
    )


def ml_features(inputs: RiskInputs) -> dict[str, float]:
    """Feature dict for the optional ML model (keys = RiskFactors raw field names)."""
    return {
        "rain_24h_mm": inputs.rain_24h_mm,
        "rain_72h_mm": inputs.rain_72h_mm,
        "max_intensity_mmph": inputs.max_intensity_mmph,
        "antecedent_7d_mm": inputs.antecedent_7d_mm,
        "discharge_ratio": inputs.gauge.ratio if inputs.gauge is not None else 0.0,
        "vulnerability": inputs.vulnerability,
    }
