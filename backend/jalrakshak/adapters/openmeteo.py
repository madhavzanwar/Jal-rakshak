"""Open-Meteo adapters: hourly precipitation (Forecast API) and GloFAS discharge (Flood API).

Both are free and keyless. Multi-location requests are used so one city needs one call per
source. Results are cached (rain 30 min, discharge 3 h) with stale fallback.
"""

from __future__ import annotations

from typing import Any

from jalrakshak.adapters.cache import CacheResult, FileCache
from jalrakshak.adapters.http import FetchError, get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
RAIN_TTL_S = 30 * 60
DISCHARGE_TTL_S = 3 * 3600

Point = tuple[float, float]


def _coords(points: list[Point]) -> tuple[str, str]:
    return (
        ",".join(f"{p[0]:.4f}" for p in points),
        ",".join(f"{p[1]:.4f}" for p in points),
    )


def _rows(data: Any, n: int) -> list[dict[str, Any]]:
    rows = data if isinstance(data, list) else [data]
    if len(rows) != n:
        raise FetchError(f"expected {n} locations, got {len(rows)}")
    return rows


async def fetch_rain(points: list[Point], cache: FileCache | None = None) -> CacheResult:
    """Hourly precipitation (mm) for each point: 7 past days + 4 forecast days, UTC.

    ``value`` is a list (one per point) of ``{"time": [iso...], "mm": [float...]}``.
    Four forecast days guarantee a full 72 h window ahead of the current hour.
    """
    lats, lons = _coords(points)

    async def fetch() -> Any:
        data = await get_json(
            FORECAST_URL,
            {
                "latitude": lats,
                "longitude": lons,
                "hourly": "precipitation",
                "past_days": 7,
                "forecast_days": 4,
                "timezone": "UTC",
            },
        )
        out = []
        for row in _rows(data, len(points)):
            hourly = row["hourly"]
            out.append(
                {
                    "time": [t + ":00Z" if len(t) == 16 else t for t in hourly["time"]],
                    "mm": [float(v or 0.0) for v in hourly["precipitation"]],
                }
            )
        return out

    return await (cache or FileCache()).get_or_fetch(f"rain:{lats}:{lons}", RAIN_TTL_S, fetch)


async def fetch_discharge(points: list[Point], cache: FileCache | None = None) -> CacheResult:
    """Daily GloFAS river discharge (m3/s): 7 past days + 7 forecast days.

    ``value`` is a list (one per point) of ``{"date": [YYYY-MM-DD...], "m3s": [float...]}``.
    """
    if not points:
        return CacheResult([], stale=False, ok=True, fetched_at=0.0)
    lats, lons = _coords(points)

    async def fetch() -> Any:
        data = await get_json(
            FLOOD_URL,
            {
                "latitude": lats,
                "longitude": lons,
                "daily": "river_discharge",
                "past_days": 7,
                "forecast_days": 7,
            },
        )
        out = []
        for row in _rows(data, len(points)):
            daily = row["daily"]
            out.append(
                {
                    "date": list(daily["time"]),
                    "m3s": [float(v or 0.0) for v in daily["river_discharge"]],
                }
            )
        return out

    key = f"discharge:{lats}:{lons}"
    return await (cache or FileCache()).get_or_fetch(key, DISCHARGE_TTL_S, fetch)
