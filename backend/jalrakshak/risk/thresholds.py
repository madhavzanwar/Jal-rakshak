"""Fixed risk-level cut-offs, IMD rainfall categories and river-gauge status (pure)."""

from __future__ import annotations

from jalrakshak.models import GaugeStatus, RiskLevel, RiverGauge

#: Score cut-offs (0-100): green < 30 <= yellow < 55 <= orange < 75 <= red.
YELLOW_MIN = 30.0
ORANGE_MIN = 55.0
RED_MIN = 75.0

_RANK: dict[RiskLevel, int] = {"green": 0, "yellow": 1, "orange": 2, "red": 3}

#: IMD 24-hour rainfall categories (lower bound in mm, label).
IMD_CATEGORIES: list[tuple[float, str]] = [
    (204.5, "extremely heavy"),
    (115.6, "very heavy"),
    (64.5, "heavy"),
    (15.6, "moderate"),
    (2.5, "light"),
    (0.1, "very light"),
]


def level_for(score: float) -> RiskLevel:
    """Map a 0-100 score to a risk level using the fixed cut-offs."""
    if score >= RED_MIN:
        return "red"
    if score >= ORANGE_MIN:
        return "orange"
    if score >= YELLOW_MIN:
        return "yellow"
    return "green"


def level_rank(level: RiskLevel) -> int:
    """green=0, yellow=1, orange=2, red=3."""
    return _RANK[level]


def max_level(*levels: RiskLevel) -> RiskLevel:
    return max(levels, key=level_rank)


def imd_category(rain_24h_mm: float) -> str:
    """IMD descriptive category for a 24-hour rainfall total ("no rain" below 0.1 mm)."""
    for lower, label in IMD_CATEGORIES:
        if rain_24h_mm >= lower:
            return label
    return "no rain"


def gauge_status(discharge_m3s: float, gauge: RiverGauge) -> GaugeStatus:
    """Classify a discharge against the gauge's GloFAS percentile thresholds."""
    if discharge_m3s >= gauge.extreme_m3s:
        return "extreme"
    if discharge_m3s >= gauge.danger_m3s:
        return "danger"
    if discharge_m3s >= gauge.warning_m3s:
        return "warning"
    return "normal"
