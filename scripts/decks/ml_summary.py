"""Turn backend/models/backtest.json into honest metric tiles for the ML slide.

The schema is owned by the backend; we read the held-out *test* split and prefer the realistic
"noisy forecast" scenario over the "perfect forecast" upper bound.
"""
from __future__ import annotations


def _f(v: float) -> str:
    return f"{v:.2f}"


def summarise(bt: dict) -> tuple[list[dict], str]:
    test = bt.get("test", {})
    noisy, pers, perfect = test.get("noisy"), test.get("persistence"), test.get("perfect")
    if not (noisy and pers):
        return ([{"value": "see MODEL.md", "label": "Backtest present but in an unexpected format"}],
                "Read from backend/models/backtest.json.")
    lg, rs = noisy["lightgbm"], noisy["rule_score"]
    split = bt.get("split", {})
    test_years = split.get("test", "2021–2024").replace("..", " to ")
    tiles = [
        {"value": f"{_f(lg['pr_auc'])} vs {_f(rs['pr_auc'])}",
         "label": "PR-AUC, LightGBM vs our rule score (realistic noisy forecasts)"},
        {"value": f"{_f(lg['at_val_threshold']['f1'])} vs {_f(rs['at_val_threshold']['f1'])}",
         "label": "F1 at the threshold chosen on 2019–20 validation (noisy forecasts)"},
        {"value": f"{_f(pers['lightgbm']['pr_auc'])} vs {_f(pers['rule_score']['pr_auc'])}",
         "label": "PR-AUC with persistence inputs (no-skill lower bound)"},
        {"value": f"{lg['base_rate'] * 100:.1f}%",
         "label": f"flood-days in the test set ({lg['n']:,} city-days)", "color": "4A5D73"},
    ]
    note = (f"Held-out test {test_years}. Labels are a proxy (GloFAS discharge > P98 or ≥115.6 mm rain), built "
            f"from the same variables, so the perfect-forecast PR-AUC of {_f(perfect['lightgbm']['pr_auc'])} is an "
            "upper bound, not real-world skill. ML adds a modest gain over the transparent score.")
    return tiles, note
