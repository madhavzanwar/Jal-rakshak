"""Feature definition shared by training and runtime inference.

Pure Python (no pandas / lightgbm) so the runtime predictor can import it cheaply.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

# Order matters: it is the column order of the LightGBM model.
FEATURE_ORDER: tuple[str, ...] = (
    "rain_24h_mm",
    "rain_72h_mm",
    "max_intensity_mmph",
    "antecedent_7d_mm",
    "discharge_ratio",
    "vulnerability",
    "month_sin",
    "month_cos",
)

# RiskFactors raw fields the caller must provide (month features are optional).
RAW_FIELDS: tuple[str, ...] = FEATURE_ORDER[:6]

# IMD "very heavy rain" threshold for 24 h accumulation (mm).
IMD_VERY_HEAVY_MM = 115.6

# Vulnerability is a ward attribute; history has no ward data so training uses a constant.
TRAINING_VULNERABILITY = 0.5


def month_encoding(month: int) -> tuple[float, float]:
    """Cyclic encoding of a calendar month (1..12)."""
    angle = 2.0 * math.pi * (month - 1) / 12.0
    return math.sin(angle), math.cos(angle)


def to_vector(features: Mapping[str, float], month: int | None = None) -> list[float]:
    """Build a model input row in ``FEATURE_ORDER``.

    Missing raw fields raise ``KeyError``; non-finite values become NaN (LightGBM treats
    NaN as missing). ``month_sin``/``month_cos`` are taken from ``features`` if present,
    else derived from ``month``; if neither is available they are NaN.
    """
    row: list[float] = []
    for name in RAW_FIELDS:
        row.append(_finite(float(features[name])))
    if "month_sin" in features and "month_cos" in features:
        row.extend([_finite(float(features["month_sin"])), _finite(float(features["month_cos"]))])
    elif month is not None:
        s, c = month_encoding(month)
        row.extend([s, c])
    else:
        row.extend([math.nan, math.nan])
    return row


def _finite(x: float) -> float:
    return x if math.isfinite(x) else math.nan
