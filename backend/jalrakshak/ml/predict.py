"""Runtime predictor: optional LightGBM P(flood-day within the next 1-3 days).

The model is strictly optional. ``flood_probability`` returns ``None`` (never raises) when
lightgbm is not installed, the model file is missing/corrupt, or the input is unusable.
The model artefacts live in ``backend/models`` (override with env ``JR_MODEL_DIR``).
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jalrakshak.ml.features import FEATURE_ORDER, to_vector

log = logging.getLogger(__name__)

MODEL_FILE = "flood_lgbm.txt"
META_FILE = "model_meta.json"

_lock = threading.Lock()
_loaded = False
_booster: Any = None
_meta: dict[str, Any] | None = None


def model_dir() -> Path:
    env = os.environ.get("JR_MODEL_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "models"


def _load() -> tuple[Any, dict[str, Any] | None]:
    global _loaded, _booster, _meta
    if _loaded:
        return _booster, _meta
    with _lock:
        if _loaded:
            return _booster, _meta
        _loaded = True
        path = model_dir() / MODEL_FILE
        try:
            meta_path = model_dir() / META_FILE
            _meta = json.loads(meta_path.read_text()) if meta_path.is_file() else None
        except (OSError, ValueError) as exc:
            log.warning("ml: cannot read model meta: %s", exc)
            _meta = None
        if not path.is_file():
            log.info("ml: model file %s not found; ML probability disabled", path)
            return None, _meta
        try:
            import lightgbm as lgb
        except ImportError:
            log.info("ml: lightgbm not installed; ML probability disabled")
            return None, _meta
        try:
            booster = lgb.Booster(model_file=str(path))
            names = list(booster.feature_name())
            if names != list(FEATURE_ORDER):
                log.warning("ml: model features %s != expected %s", names, FEATURE_ORDER)
                return None, _meta
            _booster = booster
        except Exception as exc:  # corrupt file, version mismatch, ...
            log.warning("ml: failed to load model: %s", exc)
            _booster = None
        return _booster, _meta


def reset_cache() -> None:
    """Forget the loaded model (used by tests and after retraining)."""
    global _loaded, _booster, _meta
    with _lock:
        _loaded = False
        _booster = None
        _meta = None


def model_info() -> dict[str, Any] | None:
    """Model metadata (feature order, threshold, metrics) or None if no model is usable."""
    booster, meta = _load()
    return meta if booster is not None else None


def flood_probability(city_id: str, features: Mapping[str, float]) -> float | None:
    """P(a proxy flood-day occurs in the next 1-3 days) for ``city_id``.

    ``features`` takes the RiskFactors raw fields (``rain_24h_mm``, ``rain_72h_mm``,
    ``max_intensity_mmph``, ``antecedent_7d_mm``, ``discharge_ratio``, ``vulnerability``)
    computed from the 72 h forecast window. Optional ``month`` (1..12) or
    ``month_sin``/``month_cos``; defaults to the current UTC month.
    The model is shared across cities; ``city_id`` is accepted for logging/future use.
    """
    try:
        booster, _ = _load()
        if booster is None:
            return None
        month_raw = features.get("month")
        month = int(month_raw) if month_raw is not None else datetime.now(UTC).month
        if not 1 <= month <= 12:
            month = datetime.now(UTC).month
        row = to_vector(features, month=month)
        import numpy as np

        pred = booster.predict(np.asarray([row], dtype=np.float64))
        p = float(pred[0])
        if not math.isfinite(p):
            return None
        return min(1.0, max(0.0, p))
    except Exception as exc:  # never break the risk pipeline
        log.warning("ml: prediction failed for %s: %s", city_id, exc)
        return None
