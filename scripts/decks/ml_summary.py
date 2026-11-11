"""Turn backend/models/backtest.json into metric tiles. Kept tolerant: the schema is owned by the backend."""
from __future__ import annotations


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def summarise(bt: dict) -> tuple[list[dict], str]:
    flat = {}

    def walk(d, prefix=""):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, f"{prefix}{k}.")
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                flat[f"{prefix}{k}"] = v

    walk(bt)
    tiles = []
    for key, v in list(flat.items())[:4]:
        tiles.append({"value": _fmt(v), "label": key})
    return tiles, "Read from backend/models/backtest.json."
