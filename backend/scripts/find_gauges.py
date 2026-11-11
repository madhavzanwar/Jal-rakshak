"""Empirically pick a GloFAS grid cell per city and derive discharge thresholds.

Method (documented in RISK_FORMULA.md):

1. For each city, probe a small grid of candidate points (0.05 deg GloFAS resolution) around a
   known point on the main river, using one multi-location Open-Meteo Flood API request for a
   recent full year (2023). Keep the cell with the largest mean ``river_discharge`` -- that is
   the cell on the main channel rather than a tributary or a land cell.
2. Fetch the GloFAS reanalysis daily discharge for 1995-01-01..2024-12-31 for that cell (one
   request per gauge) and derive thresholds from the empirical distribution:
   warning = P90, danger = P98, extreme = P99.7.
3. Cells whose P98 is below ``MIN_DANGER_M3S`` are not meaningful rivers at GloFAS resolution
   (small urban rivers such as the Mithi); such cities get no gauge and rely on rainfall.

Writes ``jalrakshak/data/gauges.json``. Run: ``python scripts/find_gauges.py``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jalrakshak.data.cities import CITY_RIVERS  # noqa: E402

FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
OUT = ROOT / "jalrakshak" / "data" / "gauges.json"
MIN_DANGER_M3S = 50.0
STEP = 0.05

# city -> (lat, lon, grid half-width in steps). Big rivers get a wider search.
HINTS: dict[str, tuple[float, float, int]] = {
    "mumbai": (19.07, 72.88, 1),
    "chennai": (13.01, 80.24, 1),
    "guwahati": (26.19, 91.74, 2),
    "patna": (25.63, 85.15, 2),
    "kochi": (10.11, 76.35, 1),
    "srinagar": (34.07, 74.80, 2),
    "kolkata": (22.57, 88.34, 1),
    "bhubaneswar": (20.33, 85.88, 2),
    "surat": (21.20, 72.82, 1),
    "hyderabad": (17.37, 78.48, 1),
    "pune": (18.53, 73.87, 1),
    "dibrugarh": (27.50, 94.92, 2),
}


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=120,
        verify=os.environ.get("SSL_CERT_FILE") or True,
        headers={"User-Agent": "JalRakshak/0.1 (hackathon prototype)"},
    )


def _get(client: httpx.Client, params: dict[str, Any]) -> Any:
    for attempt in range(4):
        try:
            r = client.get(FLOOD_URL, params=params)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            print(f"  retry {attempt + 1}: {exc}", file=sys.stderr)
            time.sleep(2 + attempt * 3)
    raise RuntimeError("flood API unavailable")


def probe(client: httpx.Client, lat: float, lon: float, half: int) -> tuple[float, float, float]:
    """Return (lat, lon, mean) of the candidate cell with the largest mean discharge."""
    pts = [
        (round(lat + i * STEP, 3), round(lon + j * STEP, 3))
        for i in range(-half, half + 1)
        for j in range(-half, half + 1)
    ]
    data = _get(
        client,
        {
            "latitude": ",".join(str(p[0]) for p in pts),
            "longitude": ",".join(str(p[1]) for p in pts),
            "daily": "river_discharge",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        },
    )
    rows = data if isinstance(data, list) else [data]
    best = (lat, lon, -1.0)
    for (plat, plon), row in zip(pts, rows, strict=True):
        vals = [v for v in row["daily"]["river_discharge"] if v is not None]
        mean = float(np.mean(vals)) if vals else 0.0
        if mean > best[2]:
            best = (plat, plon, mean)
    return best


def thresholds(client: httpx.Client, lat: float, lon: float) -> dict[str, float]:
    data = _get(
        client,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "river_discharge",
            "start_date": "1995-01-01",
            "end_date": "2024-12-31",
        },
    )
    arr = np.array([v for v in data["daily"]["river_discharge"] if v is not None], dtype=float)
    return {
        "n_days": int(arr.size),
        "mean_m3s": round(float(arr.mean()), 1),
        "p80_m3s": round(float(np.percentile(arr, 80)), 1),
        "warning_m3s": round(float(np.percentile(arr, 90)), 1),
        "danger_m3s": round(float(np.percentile(arr, 98)), 1),
        "extreme_m3s": round(float(np.percentile(arr, 99.7)), 1),
        "max_m3s": round(float(arr.max()), 1),
    }


def main() -> None:
    gauges: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, Any] = {}
    with _client() as client:
        for city_id, (lat, lon, half) in HINTS.items():
            river = CITY_RIVERS[city_id]
            plat, plon, mean = probe(client, lat, lon, half)
            th = thresholds(client, plat, plon)
            meaningful = th["danger_m3s"] >= MIN_DANGER_M3S
            print(f"{city_id:12s} {river:18s} cell=({plat},{plon}) mean2023={mean:9.1f} {th}")
            diagnostics[city_id] = {
                "river": river,
                "lat": plat,
                "lon": plon,
                "mean_2023_m3s": round(mean, 1),
                "meaningful": meaningful,
                **th,
            }
            if meaningful:
                gauges[city_id] = [
                    {
                        "id": f"{city_id}-{river.lower().split('-')[0]}",
                        "river": river,
                        "lat": plat,
                        "lon": plon,
                        "warning_m3s": th["warning_m3s"],
                        "danger_m3s": th["danger_m3s"],
                        "extreme_m3s": th["extreme_m3s"],
                    }
                ]
            time.sleep(1)
    OUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "method": (
                    "GloFAS v4 reanalysis daily river_discharge 1995-2024 via Open-Meteo Flood "
                    "API; warning=P90, danger=P98, extreme=P99.7; cell = max mean discharge in "
                    f"a {STEP} deg candidate grid; cells with P98 < {MIN_DANGER_M3S} m3/s dropped"
                ),
                "gauges": gauges,
                "diagnostics": diagnostics,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
