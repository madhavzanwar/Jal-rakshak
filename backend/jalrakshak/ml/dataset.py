"""Historical dataset builder for the optional flood-day model (training-time only).

Data sources (public, no key):
  * Open-Meteo Flood API  - GloFAS v4 reanalysis daily ``river_discharge`` (0.05 deg grid).
  * Open-Meteo Archive API - ERA5 / ERA5-Land reanalysis hourly ``precipitation``.

Raw responses are cached as JSON under ``backend/var/ml_cache`` (gitignored).
Requires the ``ml`` extra (pandas). Never imported by the runtime predictor.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd

from jalrakshak.ml.features import (
    FEATURE_ORDER,
    IMD_VERY_HEAVY_MM,
    TRAINING_VULNERABILITY,
    month_encoding,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(os.environ.get("JR_ML_CACHE", BACKEND_DIR / "var" / "ml_cache"))

FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "jalrakshak-ml/0.1 (hackathon research; open-meteo non-commercial)"

START_DATE = "1991-01-01"
END_DATE = "2024-12-31"
CLIMATOLOGY_END = "2018-12-31"  # thresholds use the training period only (no test leakage)
DISCHARGE_PERCENTILE = 98.0


@dataclass(frozen=True)
class CitySpec:
    id: str
    name: str
    lat: float  # city centre (rainfall)
    lon: float
    river: str
    river_lat: float  # search centre for the main river cell
    river_lon: float
    radius_deg: float = 0.15


CITIES: tuple[CitySpec, ...] = (
    CitySpec("mumbai", "Mumbai", 19.0760, 72.8777, "Ulhas", 19.20, 73.05, 0.20),
    CitySpec("chennai", "Chennai", 13.0827, 80.2707, "Adyar/Cooum", 13.05, 80.20, 0.20),
    CitySpec("guwahati", "Guwahati", 26.1445, 91.7362, "Brahmaputra", 26.19, 91.74),
    CitySpec("patna", "Patna", 25.5941, 85.1376, "Ganga", 25.62, 85.15),
    CitySpec("kochi", "Kochi", 9.9312, 76.2673, "Periyar", 10.10, 76.30, 0.20),
    CitySpec("srinagar", "Srinagar", 34.0837, 74.7973, "Jhelum", 34.08, 74.80),
    CitySpec("kolkata", "Kolkata", 22.5726, 88.3639, "Hooghly", 22.57, 88.33),
    CitySpec("bhubaneswar", "Bhubaneswar", 20.2961, 85.8245, "Mahanadi", 20.40, 85.85, 0.20),
    CitySpec("surat", "Surat", 21.1702, 72.8311, "Tapi", 21.20, 72.82),
    CitySpec("hyderabad", "Hyderabad", 17.3850, 78.4867, "Musi", 17.37, 78.48),
    CitySpec("pune", "Pune", 18.5204, 73.8567, "Mula-Mutha", 18.53, 73.87),
    CitySpec("dibrugarh", "Dibrugarh", 27.4728, 94.9120, "Brahmaputra", 27.49, 94.91),
)


# --------------------------------------------------------------------------- HTTP + cache


def _client() -> httpx.Client:
    verify: str | bool = True
    ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
    if Path(ca).is_file():
        verify = ca
    return httpx.Client(
        timeout=httpx.Timeout(300.0, connect=60.0),
        verify=verify,
        headers={"User-Agent": USER_AGENT},
        trust_env=True,
    )


def _get_json(url: str, params: dict[str, str], cache_name: str, retries: int = 5) -> Any:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name
    if path.is_file():
        return json.loads(path.read_text())
    last: Exception | None = None
    with _client() as client:
        for attempt in range(retries):
            try:
                resp = client.get(url, params=params)
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
                resp.raise_for_status()
                data = resp.json()
                path.write_text(json.dumps(data))
                time.sleep(1.0)  # be polite: strictly sequential, spaced requests
                return data
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
                time.sleep(min(60.0, 5.0 * 2**attempt))
    raise RuntimeError(f"failed to fetch {url} {params}: {last}")


# --------------------------------------------------------------------------- river cell probe


def probe_river_cell(spec: CitySpec, step: float = 0.05) -> tuple[float, float, float]:
    """Return (lat, lon, mean discharge) of the grid cell with the largest mean discharge
    within ``radius_deg`` of the river search centre (one multi-location request)."""
    n = round(spec.radius_deg / step)
    lats: list[float] = []
    lons: list[float] = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            lats.append(round(spec.river_lat + i * step, 3))
            lons.append(round(spec.river_lon + j * step, 3))
    data = _get_json(
        FLOOD_URL,
        {
            "latitude": ",".join(map(str, lats)),
            "longitude": ",".join(map(str, lons)),
            "daily": "river_discharge",
            "start_date": "2010-01-01",
            "end_date": "2018-12-31",
        },
        f"probe_{spec.id}.json",
    )
    items = data if isinstance(data, list) else [data]
    best = (spec.river_lat, spec.river_lon, -1.0)
    for item in items:
        vals = [v for v in item["daily"]["river_discharge"] if v is not None]
        if not vals:
            continue
        mean = float(np.mean(vals))
        if mean > best[2]:
            best = (float(item["latitude"]), float(item["longitude"]), mean)
    return best


@dataclass(frozen=True)
class GaugeSpec:
    lat: float
    lon: float
    river: str
    warning_m3s: float
    danger_m3s: float
    extreme_m3s: float


def load_gauges() -> dict[str, GaugeSpec] | None:
    """Primary gauge per city from the backend's ``jalrakshak/data/gauges.json``.

    Returns None if the file is absent/unreadable (then cells are probed here). A city that is
    missing from an existing file has no gauge at runtime (discharge_ratio = 0), and training
    mirrors that.
    """
    path = BACKEND_DIR / "jalrakshak" / "data" / "gauges.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if isinstance(raw, dict) and isinstance(raw.get("gauges"), dict):
        raw = raw["gauges"]
    if not isinstance(raw, dict):
        return None
    out: dict[str, GaugeSpec] = {}
    for city_id, val in raw.items():
        g = val[0] if isinstance(val, list) and val else val
        if not isinstance(g, dict):
            continue
        try:
            out[city_id] = GaugeSpec(
                float(g["lat"]),
                float(g["lon"]),
                str(g.get("river", "")),
                float(g["warning_m3s"]),
                float(g["danger_m3s"]),
                float(g["extreme_m3s"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------- raw series


def fetch_discharge(city_id: str, lat: float, lon: float) -> pd.Series:
    data = _get_json(
        FLOOD_URL,
        {
            "latitude": f"{lat:.3f}",
            "longitude": f"{lon:.3f}",
            "daily": "river_discharge",
            "start_date": START_DATE,
            "end_date": END_DATE,
        },
        f"discharge_{city_id}_{lat:.3f}_{lon:.3f}.json",
    )
    d = data["daily"]
    s = pd.Series(d["river_discharge"], index=pd.to_datetime(d["time"]), dtype="float64")
    return s.rename("discharge")


def fetch_rain_hourly(city_id: str, lat: float, lon: float) -> pd.Series:
    """Hourly precipitation (mm), local time (Asia/Kolkata), fetched in 5-year chunks."""
    parts: list[pd.Series] = []
    start = int(START_DATE[:4])
    end = int(END_DATE[:4])
    for y0 in range(start, end + 1, 5):
        y1 = min(end, y0 + 4)
        data = _get_json(
            ARCHIVE_URL,
            {
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "hourly": "precipitation",
                "start_date": f"{y0}-01-01",
                "end_date": f"{y1}-12-31",
                "timezone": "Asia/Kolkata",
            },
            f"rain_{city_id}_{y0}_{y1}.json",
        )
        h = data["hourly"]
        parts.append(
            pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]), dtype="float64")
        )
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated()]
    return s.rename("rain")


# --------------------------------------------------------------------------- dataset


@dataclass
class CityData:
    spec: CitySpec
    gauge: GaugeSpec | None  # thresholds used for discharge_ratio / the rule baseline
    gauge_source: str
    mean_discharge: float
    p98_m3s: float  # label threshold (training-period climatology)
    frame: pd.DataFrame


def build_city_frame(
    rain_h: pd.Series, discharge: pd.Series | None, danger_m3s: float | None, p98_m3s: float | None
) -> pd.DataFrame:
    """One row per issue day d (forecast issued at 00:00 local on d+1).

    Window W = the next 72 h (days d+1..d+3). "Perfect forecast" features use the realised
    values in W; ``*_persist`` columns use the previous 72 h (days d-2..d) as a no-skill
    persistence forecast. Target = any flood-day in d+1..d+3.
    """
    rain_h = rain_h.fillna(0.0)
    roll24 = rain_h.rolling(24, min_periods=1).sum()
    # Daily aggregates on local calendar days.
    day_sum = rain_h.resample("D").sum()
    day_max_h = rain_h.resample("D").max()
    day_max_roll24 = roll24.resample("D").max()  # max 24h sum ending within that day
    idx = day_sum.index
    has_gauge = discharge is not None and danger_m3s is not None and p98_m3s is not None
    q = discharge.reindex(idx) if discharge is not None else pd.Series(np.nan, index=idx)
    danger = danger_m3s if danger_m3s else 1.0
    p98 = p98_m3s if p98_m3s is not None else np.inf

    def fwd(s: pd.Series, how: str) -> pd.Series:
        # value over days d+1..d+3
        shifted = [s.shift(-k) for k in (1, 2, 3)]
        stacked = pd.concat(shifted, axis=1)
        return stacked.sum(axis=1, min_count=3) if how == "sum" else stacked.max(axis=1)

    def back(s: pd.Series, how: str) -> pd.Series:
        stacked = pd.concat([s.shift(k) for k in (0, 1, 2)], axis=1)
        return stacked.sum(axis=1, min_count=3) if how == "sum" else stacked.max(axis=1)

    # max rolling-24h within the window: rolling sums ending in d+1..d+3, but a 24h sum
    # ending early on d+1 includes hours of day d; the bias is small and identical at
    # runtime (where the backend takes the max rolling 24h over the 72h forecast window).
    f = pd.DataFrame(index=idx)
    f["rain_24h_mm"] = fwd(day_max_roll24, "max")
    f["rain_72h_mm"] = fwd(day_sum, "sum")
    f["max_intensity_mmph"] = fwd(day_max_h, "max")
    f["antecedent_7d_mm"] = day_sum.rolling(7, min_periods=7).sum()
    f["discharge_ratio"] = fwd(q, "max") / danger if has_gauge else 0.0
    f["vulnerability"] = TRAINING_VULNERABILITY
    months = pd.DatetimeIndex(idx).month
    enc = np.array([month_encoding(int(m)) for m in months])
    f["month_sin"] = enc[:, 0]
    f["month_cos"] = enc[:, 1]

    # Persistence ("no forecast") variant: previous 72 h stand in for the next 72 h.
    f["rain_24h_mm_persist"] = back(day_max_roll24, "max")
    f["rain_72h_mm_persist"] = back(day_sum, "sum")
    f["max_intensity_mmph_persist"] = back(day_max_h, "max")
    f["discharge_ratio_persist"] = back(q, "max") / danger if has_gauge else 0.0

    rain_flag: pd.Series = day_sum >= IMD_VERY_HEAVY_MM
    river_flag: pd.Series
    flood_day: pd.Series
    if has_gauge:
        river_flag = (q > p98).astype("float64").where(q.notna())
        either = (river_flag.fillna(0.0) > 0) | rain_flag
        flood_day = either.astype("float64").where(q.notna() | rain_flag)
    else:
        river_flag = pd.Series(0.0, index=idx)
        flood_day = rain_flag.astype("float64")
    f["flood_day"] = flood_day
    f["flood_day_rain"] = rain_flag.astype("float64")
    f["flood_day_river"] = river_flag
    target = pd.concat([f["flood_day"].shift(-k) for k in (1, 2, 3)], axis=1)
    f["target"] = target.max(axis=1).where(target.notna().all(axis=1))
    f["rain_day_mm"] = day_sum
    f["discharge_m3s"] = q
    return f.dropna(subset=[*FEATURE_ORDER, "target"])


def build_dataset(verbose: bool = True) -> tuple[pd.DataFrame, list[CityData]]:
    gauges = load_gauges()
    frames: list[pd.DataFrame] = []
    cities: list[CityData] = []
    for spec in CITIES:
        gauge: GaugeSpec | None
        if gauges is not None:
            gauge = gauges.get(spec.id)
            source = "gauges.json" if gauge else "none (not in gauges.json)"
        else:
            glat, glon, _ = probe_river_cell(spec)
            gauge = GaugeSpec(glat, glon, spec.river, np.nan, np.nan, np.nan)
            source = "probe"
        rain = fetch_rain_hourly(spec.id, spec.lat, spec.lon)
        if gauge is not None:
            q = fetch_discharge(spec.id, gauge.lat, gauge.lon)
            clim = q[:CLIMATOLOGY_END].dropna()
            p98_val = float(np.percentile(clim, DISCHARGE_PERCENTILE))
            p98: float | None = p98_val
            mean_q = float(clim.mean())
            if source == "probe":  # derive thresholds like the backend does (P90/P98/P99.7)
                gauge = GaugeSpec(
                    gauge.lat,
                    gauge.lon,
                    spec.river,
                    float(np.percentile(clim, 90)),
                    p98_val,
                    float(np.percentile(clim, 99.7)),
                )
            frame = build_city_frame(rain, q, gauge.danger_m3s, p98)
        else:
            p98, mean_q = None, float("nan")
            frame = build_city_frame(rain, None, None, None)
        frame.insert(0, "city_id", spec.id)
        frames.append(frame)
        cities.append(CityData(spec, gauge, source, mean_q, p98 or float("nan"), frame))
        if verbose:
            g = f"{gauge.lat:.3f},{gauge.lon:.3f} danger={gauge.danger_m3s:9.1f}" if gauge else "-"
            print(
                f"{spec.id:12s} gauge[{source}] {g} p98_train={p98 or float('nan'):9.1f}"
                f" rows={len(frame)} pos={frame['target'].mean():.3f}"
            )
    df = pd.concat(frames)
    df.index.name = "date"
    return df.reset_index(), cities
