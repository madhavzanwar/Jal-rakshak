"""Tests for the optional LightGBM flood-day predictor (jalrakshak.ml)."""

from __future__ import annotations

import importlib.util
import itertools
from collections.abc import Iterator
from pathlib import Path

import pytest

from jalrakshak.ml import predict
from jalrakshak.ml.features import FEATURE_ORDER, to_vector

HAS_LGB = importlib.util.find_spec("lightgbm") is not None
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / predict.MODEL_FILE

BASE: dict[str, float] = {
    "rain_24h_mm": 60.0,
    "rain_72h_mm": 110.0,
    "max_intensity_mmph": 15.0,
    "antecedent_7d_mm": 80.0,
    "discharge_ratio": 0.6,
    "vulnerability": 0.5,
    "month": 7,
}


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    predict.reset_cache()
    yield
    predict.reset_cache()


def test_feature_vector_order() -> None:
    row = to_vector(BASE, month=7)
    assert len(row) == len(FEATURE_ORDER)
    assert row[FEATURE_ORDER.index("discharge_ratio")] == 0.6


def test_returns_none_when_model_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JR_MODEL_DIR", str(tmp_path))
    assert predict.flood_probability("guwahati", BASE) is None
    assert predict.model_info() is None


def test_returns_none_on_corrupt_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / predict.MODEL_FILE).write_text("not a model")
    monkeypatch.setenv("JR_MODEL_DIR", str(tmp_path))
    assert predict.flood_probability("guwahati", BASE) is None


def test_returns_none_on_bad_input() -> None:
    assert predict.flood_probability("guwahati", {"rain_24h_mm": 1.0}) is None


needs_model = pytest.mark.skipif(
    not HAS_LGB or not MODEL_PATH.is_file(), reason="lightgbm or trained model not available"
)


@needs_model
def test_probability_in_unit_interval() -> None:
    for ratio in (0.0, 0.5, 1.0, 2.0):
        p = predict.flood_probability("patna", {**BASE, "discharge_ratio": ratio})
        assert p is not None
        assert 0.0 <= p <= 1.0
    info = predict.model_info()
    assert info is not None
    assert info["feature_order"] == list(FEATURE_ORDER)


@needs_model
def test_month_defaults_when_missing() -> None:
    feats = {k: v for k, v in BASE.items() if k != "month"}
    p = predict.flood_probability("kochi", feats)
    assert p is not None and 0.0 <= p <= 1.0


@needs_model
def test_monotone_in_discharge_ratio() -> None:
    probs = []
    for ratio in (0.2, 0.6, 0.9, 1.1, 1.5):
        p = predict.flood_probability("guwahati", {**BASE, "discharge_ratio": ratio})
        assert p is not None
        probs.append(p)
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(probs))
    assert probs[-1] > probs[0] + 0.3


@needs_model
def test_monotone_in_rain() -> None:
    lo = predict.flood_probability("mumbai", {**BASE, "discharge_ratio": 0.0, "rain_24h_mm": 20})
    hi = predict.flood_probability("mumbai", {**BASE, "discharge_ratio": 0.0, "rain_24h_mm": 250})
    assert lo is not None and hi is not None
    assert hi >= lo
