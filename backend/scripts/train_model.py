"""Train + backtest the optional LightGBM flood-day model.

Usage (from ``backend/``, with the ``ml`` extra installed)::

    pip install -e '.[ml]'
    python scripts/train_model.py            # fetches/caches data, trains, writes artefacts

Writes ``models/flood_lgbm.txt``, ``models/model_meta.json``, ``models/backtest.json`` and
``../docs/img/model_pr_curve.png``. See ``docs/MODEL.md`` for the method and caveats.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from jalrakshak.ml.dataset import (  # noqa: E402
    ARCHIVE_URL,
    CLIMATOLOGY_END,
    DISCHARGE_PERCENTILE,
    FLOOD_URL,
    CityData,
    build_dataset,
)
from jalrakshak.ml.features import FEATURE_ORDER, IMD_VERY_HEAVY_MM  # noqa: E402
from jalrakshak.risk.scoring import GaugeRef, RiskInputs, score_ward  # noqa: E402

MODELS = BACKEND / "models"
PLOT = BACKEND.parent / "docs" / "img" / "model_pr_curve.png"

TRAIN_END = "2018-12-31"
VAL_START, VAL_END = "2019-01-01", "2020-12-31"
TEST_START = "2021-01-01"
BASELINE_CUTOFF = 55.0  # "orange" on the transparent score
SEED = 42

# Monotone constraints: more rain / wetter ground / higher river never lowers P(flood).
MONOTONE = {
    "rain_24h_mm": 1,
    "rain_72h_mm": 1,
    "max_intensity_mmph": 1,
    "antecedent_7d_mm": 1,
    "discharge_ratio": 1,
    "vulnerability": 0,
    "month_sin": 0,
    "month_cos": 0,
}

PARAMS: dict[str, Any] = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "monotone_constraints": [MONOTONE[f] for f in FEATURE_ORDER],
    "monotone_constraints_method": "advanced",
    "verbosity": -1,
    "seed": SEED,
    "deterministic": True,
    "num_threads": 4,
}

PERSIST = {
    "rain_24h_mm": "rain_24h_mm_persist",
    "rain_72h_mm": "rain_72h_mm_persist",
    "max_intensity_mmph": "max_intensity_mmph_persist",
    "discharge_ratio": "discharge_ratio_persist",
}


def predict(booster: lgb.Booster, x: pd.DataFrame) -> np.ndarray:
    return np.asarray(booster.predict(x, num_iteration=booster.best_iteration), dtype=float)


# --------------------------------------------------------------------------- scenarios


def scenario(df: pd.DataFrame, name: str, rng: np.random.Generator) -> pd.DataFrame:
    """Feature frame under a forecast-quality scenario (target unchanged)."""
    out = df.copy()
    if name == "perfect":
        return out
    if name == "noisy":
        # Multiplicative log-normal error, one draw per issue day (shared by the 3 rain
        # fields) - a crude stand-in for NWP rainfall and GloFAS forecast error.
        e_rain = np.exp(rng.normal(-0.18, 0.6, len(out)))  # median bias ~ -16% (under-forecast)
        e_q = np.exp(rng.normal(0.0, 0.15, len(out)))
        for col in ("rain_24h_mm", "rain_72h_mm", "max_intensity_mmph"):
            out[col] = out[col] * e_rain
        out["discharge_ratio"] = out["discharge_ratio"] * e_q
        return out
    if name == "persistence":
        for col, src in PERSIST.items():
            out[col] = out[src]
        return out
    raise ValueError(name)


# --------------------------------------------------------------------------- baseline


def baseline_scores(df: pd.DataFrame, cities: dict[str, CityData]) -> np.ndarray:
    """Transparent rule score (jalrakshak.risk.scoring.score_ward), vulnerability 0.5."""
    out = np.empty(len(df))
    cols = zip(
        df["city_id"].astype(str),
        df["rain_24h_mm"].to_numpy(dtype=float),
        df["rain_72h_mm"].to_numpy(dtype=float),
        df["max_intensity_mmph"].to_numpy(dtype=float),
        df["antecedent_7d_mm"].to_numpy(dtype=float),
        df["discharge_ratio"].to_numpy(dtype=float),
        df["vulnerability"].to_numpy(dtype=float),
        strict=True,
    )
    for i, (cid, r24, r72, mi, a7, ratio, vul) in enumerate(cols):
        g = cities[cid].gauge
        gauge = None
        if g is not None:
            gauge = GaugeRef(
                river=g.river,
                peak_m3s=float(ratio) * g.danger_m3s,
                warning_m3s=g.warning_m3s,
                danger_m3s=g.danger_m3s,
                extreme_m3s=g.extreme_m3s,
            )
        inputs = RiskInputs(
            rain_24h_mm=float(r24),
            rain_72h_mm=float(r72),
            max_intensity_mmph=float(mi),
            antecedent_7d_mm=float(a7),
            vulnerability=float(vul),
            gauge=gauge,
        )
        out[i] = score_ward(inputs).score
    return out


# --------------------------------------------------------------------------- metrics


def pr_at(y: np.ndarray, p: np.ndarray, thr: float) -> dict[str, float]:
    pred = p >= thr
    tp = float(np.sum(pred & (y == 1)))
    fp = float(np.sum(pred & (y == 0)))
    fn = float(np.sum(~pred & (y == 1)))
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec + rec and not np.isnan(prec + rec) else 0.0
    return {
        "threshold": round(thr, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "alert_rate": round(float(pred.mean()), 4),
    }


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-12, None)
    return float(thr[int(np.argmax(f1))])


def metrics(y: np.ndarray, prob: np.ndarray, thresholds: dict[str, float]) -> dict[str, Any]:
    both = len(np.unique(y)) == 2
    m: dict[str, Any] = {
        "n": len(y),
        "positives": int(y.sum()),
        "base_rate": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, prob)), 4) if both else None,
        "pr_auc": round(float(average_precision_score(y, prob)), 4) if both else None,
        "brier": round(float(brier_score_loss(y, np.clip(prob, 0, 1))), 4),
    }
    for name, thr in thresholds.items():
        m[f"at_{name}"] = pr_at(y, prob, thr)
    return m


# --------------------------------------------------------------------------- plotting


def plot(
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
    y: np.ndarray,
    p_ml: np.ndarray,
    p_base: np.ndarray,
    base_rate: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.6,
        }
    )
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), dpi=150)
    styles = {
        "LightGBM, perfect forecast": ("#1f5fae", "-"),
        "Rule score, perfect forecast": ("#d1782a", "-"),
        "LightGBM, noisy forecast": ("#1f5fae", "--"),
        "Rule score, noisy forecast": ("#d1782a", "--"),
        "LightGBM, persistence": ("#1f5fae", ":"),
        "Rule score, persistence": ("#d1782a", ":"),
    }
    for label, (yy, pp) in curves.items():
        prec, rec, _ = precision_recall_curve(yy, pp)
        ap = average_precision_score(yy, pp)
        color, ls = styles[label]
        ax1.plot(rec, prec, color=color, ls=ls, lw=1.6, label=f"{label} (AP {ap:.2f})")
    ax1.axhline(base_rate, color="#888", lw=0.8, ls="-.", label=f"base rate {base_rate:.2f}")
    ax1.set(
        xlabel="Recall",
        ylabel="Precision",
        xlim=(0, 1),
        ylim=(0, 1.02),
        title="Precision-recall, test 2021-2024",
    )
    ax1.legend(fontsize=7.5, loc="lower left", frameon=False)

    bins = np.linspace(0, 1, 11)
    for pp, label, color in (
        (p_ml, "LightGBM", "#1f5fae"),
        (p_base, "Rule score / 100 (not a probability)", "#d1782a"),
    ):
        idx = np.clip(np.digitize(pp, bins) - 1, 0, 9)
        xs, ys, ns = [], [], []
        for b in range(10):
            mask = idx == b
            if mask.sum() >= 20:
                xs.append(pp[mask].mean())
                ys.append(y[mask].mean())
                ns.append(mask.sum())
        ax2.plot(xs, ys, marker="o", ms=4, color=color, lw=1.6, label=label)
    ax2.plot([0, 1], [0, 1], color="#888", lw=0.8, ls="-.", label="perfect calibration")
    ax2.set(
        xlabel="Predicted probability",
        ylabel="Observed frequency",
        xlim=(0, 1),
        ylim=(0, 1),
        title="Reliability, test 2021-2024 (perfect forecast)",
    )
    ax2.legend(fontsize=7.5, loc="upper left", frameon=False)
    fig.suptitle(
        "JalRakshak flood-day model: target = proxy flood-day within next 1-3 days", fontsize=10.5
    )
    fig.tight_layout()
    fig.savefig(PLOT, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2000)
    args = ap.parse_args()

    df, city_list = build_dataset()
    cities = {c.spec.id: c for c in city_list}
    df["date"] = pd.to_datetime(df["date"])
    train = df[df.date <= TRAIN_END]
    val = df[(df.date >= VAL_START) & (df.date <= VAL_END)]
    test = df[df.date >= TEST_START]
    print(
        f"rows train={len(train)} val={len(val)} test={len(test)}; "
        f"pos rate train={train.target.mean():.3f} val={val.target.mean():.3f} "
        f"test={test.target.mean():.3f}"
    )

    feats = list(FEATURE_ORDER)
    dtrain = lgb.Dataset(train[feats], label=train.target, feature_name=feats)
    dval = lgb.Dataset(val[feats], label=val.target, reference=dtrain)
    booster = lgb.train(
        PARAMS,
        dtrain,
        num_boost_round=args.rounds,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    print(f"best iteration {booster.best_iteration}")

    p_val = predict(booster, val[feats])
    thr_ml = best_f1_threshold(val.target.to_numpy(), p_val)
    b_val = baseline_scores(val, cities)
    thr_base_val = best_f1_threshold(val.target.to_numpy(), b_val / 100.0) * 100.0
    print(f"val-chosen thresholds: ml={thr_ml:.3f} baseline score={thr_base_val:.1f}")

    rng = np.random.default_rng(SEED)
    results: dict[str, Any] = {}
    curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    y_test = test.target.to_numpy()
    keep: dict[str, np.ndarray] = {}
    for scen in ("perfect", "noisy", "persistence"):
        st = scenario(test, scen, rng)
        p_ml = predict(booster, st[feats])
        s_b = baseline_scores(st, cities)
        keep[f"ml_{scen}"], keep[f"base_{scen}"] = p_ml, s_b
        results[scen] = {
            "lightgbm": metrics(y_test, p_ml, {"0.5": 0.5, "val_threshold": thr_ml}),
            "rule_score": metrics(
                y_test,
                s_b / 100.0,
                {"score_55": BASELINE_CUTOFF / 100.0, "val_threshold": thr_base_val / 100.0},
            ),
        }
        human = {
            "perfect": "perfect forecast",
            "noisy": "noisy forecast",
            "persistence": "persistence",
        }[scen]
        curves[f"LightGBM, {human}"] = (y_test, p_ml)
        curves[f"Rule score, {human}"] = (y_test, s_b / 100.0)

    # Validation metrics too (perfect forecast), for transparency.
    val_metrics = {
        "lightgbm": metrics(val.target.to_numpy(), p_val, {"0.5": 0.5, "val_threshold": thr_ml}),
        "rule_score": metrics(
            val.target.to_numpy(),
            b_val / 100.0,
            {"score_55": 0.55, "val_threshold": thr_base_val / 100.0},
        ),
    }

    per_city: dict[str, Any] = {}
    for cid in cities:
        mask = (test.city_id == cid).to_numpy()
        yy = y_test[mask]
        per_city[cid] = {
            "gauge": cities[cid].gauge_source,
            "lightgbm": metrics(yy, keep["ml_perfect"][mask], {"val_threshold": thr_ml}),
            "rule_score": metrics(yy, keep["base_perfect"][mask] / 100.0, {"score_55": 0.55}),
            "lightgbm_persistence": metrics(
                yy, keep["ml_persistence"][mask], {"val_threshold": thr_ml}
            ),
            "rule_score_persistence": metrics(
                yy, keep["base_persistence"][mask] / 100.0, {"score_55": 0.55}
            ),
        }

    plot(curves, y_test, keep["ml_perfect"], keep["base_perfect"] / 100.0, float(y_test.mean()))

    imp = dict(zip(feats, booster.feature_importance("gain").round(1).tolist(), strict=True))
    trained_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    label_def = (
        f"flood-day = GloFAS daily discharge at the city gauge cell > P{DISCHARGE_PERCENTILE:g}"
        f" of its 1997-{CLIMATOLOGY_END[:4]} climatology OR local-day rain >= "
        f"{IMD_VERY_HEAVY_MM} mm (IMD very heavy); target = any flood-day in days "
        "d+1..d+3 (proxy, not observed flood events)"
    )
    backtest: dict[str, Any] = {
        "trained_at": trained_at,
        "label": label_def,
        "split": {
            "train": f"{df.date.min().date()}..{TRAIN_END}",
            "validation": f"{VAL_START}..{VAL_END}",
            "test": f"{TEST_START}..{df.date.max().date()}",
        },
        "rows": {"train": len(train), "validation": len(val), "test": len(test)},
        "thresholds": {
            "lightgbm_val_f1": round(thr_ml, 4),
            "rule_score_fixed": BASELINE_CUTOFF,
            "rule_score_val_f1": round(thr_base_val, 1),
        },
        "scenarios_note": (
            "perfect = realised next-72h rain/discharge (upper bound); noisy = "
            "log-normal multiplicative error (rain sigma 0.6, median -16%; "
            "discharge sigma 0.15); persistence = previous 72h used as forecast "
            "(no-skill lower bound). Same perturbed inputs feed both models."
        ),
        "validation_perfect": val_metrics,
        "test": results,
        "test_per_city_perfect": per_city,
        "feature_importance_gain": imp,
        "gauges": {
            c.spec.id: {
                "source": c.gauge_source,
                "lat": c.gauge.lat if c.gauge else None,
                "lon": c.gauge.lon if c.gauge else None,
                "danger_m3s": c.gauge.danger_m3s if c.gauge else None,
                "label_p98_m3s": None if np.isnan(c.p98_m3s) else round(c.p98_m3s, 1),
            }
            for c in city_list
        },
    }

    MODELS.mkdir(exist_ok=True)
    booster.save_model(str(MODELS / "flood_lgbm.txt"), num_iteration=booster.best_iteration)
    meta = {
        "model": "LightGBM binary (gbdt), monotone-increasing in rain/antecedent/discharge",
        "lightgbm_version": lgb.__version__,
        "feature_order": feats,
        "threshold": round(thr_ml, 4),
        "threshold_rule": "max F1 on validation 2019-2020 (perfect-forecast features)",
        "num_trees": booster.best_iteration,
        "trained_at": trained_at,
        "training_range": backtest["split"]["train"],
        "validation_range": backtest["split"]["validation"],
        "test_range": backtest["split"]["test"],
        "label": label_def,
        "data_sources": {
            "discharge": f"{FLOOD_URL} (GloFAS v4 reanalysis, daily)",
            "rainfall": f"{ARCHIVE_URL} (ERA5/ERA5-Land reanalysis, hourly)",
        },
        "training_vulnerability": 0.5,
        "metrics_test": {
            s: {
                "lightgbm": {k: results[s]["lightgbm"][k] for k in ("roc_auc", "pr_auc", "brier")},
                "rule_score": {
                    k: results[s]["rule_score"][k] for k in ("roc_auc", "pr_auc", "brier")
                },
            }
            for s in results
        },
        "caveats": "proxy label; perfect-forecast training; see docs/MODEL.md",
    }
    (MODELS / "model_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (MODELS / "backtest.json").write_text(json.dumps(backtest, indent=2) + "\n")

    for scen in results:
        for model in ("lightgbm", "rule_score"):
            m = results[scen][model]
            thr_key = "at_val_threshold"
            print(
                f"{scen:12s} {model:10s} roc={m['roc_auc']} pr={m['pr_auc']} "
                f"brier={m['brier']} {thr_key}={m[thr_key]}"
            )
    print(f"model size {(MODELS / 'flood_lgbm.txt').stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
