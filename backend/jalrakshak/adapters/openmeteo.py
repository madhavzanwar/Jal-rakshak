"""Open-Meteo adapters: hourly precipitation (Forecast API) and GloFAS discharge (Flood API).

Both are free and keyless. Multi-location requests are used so one city needs one call per
source, and ``prefetch`` warms all cities with a single call per source. Results are cached
(rain 30 min, discharge 3 h) with stale fallback.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from jalrakshak.adapters.cache import CacheResult, FileCache
from jalrakshak.adapters.http import FetchError, get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
RAIN_TTL_S = 30 * 60
DISCHARGE_TTL_S = 3 * 3600

Point = tuple[float, float]
Rows = list[dict[str, Any]]


def _coords(points: list[Point]) -> tuple[str, str]:
    return (
        ",".join(f"{p[0]:.4f}" for p in points),
        ",".join(f"{p[1]:.4f}" for p in points),
    )


def _rows(data: Any, n: int) -> Rows:
    rows = data if isinstance(data, list) else [data]
    if len(rows) != n:
        raise FetchError(f"expected {n} locations, got {len(rows)}")
    return rows


def _rain_key(points: list[Point]) -> str:
    lats, lons = _coords(points)
    return f"rain:{lats}:{lons}"


def _discharge_key(points: list[Point]) -> str:
    lats, lons = _coords(points)
    return f"discharge:{lats}:{lons}"


async def _rain_request(points: list[Point]) -> Rows:
    lats, lons = _coords(points)
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
    return [
        {
            "time": [t + ":00Z" if len(t) == 16 else t for t in row["hourly"]["time"]],
            "mm": [float(v or 0.0) for v in row["hourly"]["precipitation"]],
        }
        for row in _rows(data, len(points))
    ]


async def _discharge_request(points: list[Point]) -> Rows:
    lats, lons = _coords(points)
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
    return [
        {
            "date": list(row["daily"]["time"]),
            "m3s": [float(v or 0.0) for v in row["daily"]["river_discharge"]],
        }
        for row in _rows(data, len(points))
    ]


async def fetch_rain(points: list[Point], cache: FileCache | None = None) -> CacheResult:
    """Hourly precipitation (mm) for each point: 7 past days + 4 forecast days, UTC.

    ``value`` is a list (one per point) of ``{"time": [iso...], "mm": [float...]}``.
    Four forecast days guarantee a full 72 h window ahead of the current hour.
    """

    async def fetch() -> Any:
        return await _rain_request(points)

    return await (cache or FileCache()).get_or_fetch(_rain_key(points), RAIN_TTL_S, fetch)


async def fetch_discharge(points: list[Point], cache: FileCache | None = None) -> CacheResult:
    """Daily GloFAS river discharge (m3/s): 7 past days + 7 forecast days.

    ``value`` is a list (one per point) of ``{"date": [YYYY-MM-DD...], "m3s": [float...]}``.
    """
    if not points:
        return CacheResult([], stale=False, ok=True, fetched_at=0.0)

    async def fetch() -> Any:
        return await _discharge_request(points)

    return await (cache or FileCache()).get_or_fetch(_discharge_key(points), DISCHARGE_TTL_S, fetch)


async def prefetch(rain_groups: list[list[Point]], gauge_groups: list[list[Point]]) -> None:
    """Warm per-city cache entries with ONE multi-location request per source.

    Groups whose cache entry is still fresh are skipped; failures are ignored (the per-city
    fetch then retries and falls back to stale data).
    """
    cache = FileCache()
    now = time.time()
    plan: list[
        tuple[
            Callable[[list[Point]], str],
            float,
            Callable[[list[Point]], Awaitable[Rows]],
            list[list[Point]],
        ]
    ] = [
        (_rain_key, RAIN_TTL_S, _rain_request, rain_groups),
        (_discharge_key, DISCHARGE_TTL_S, _discharge_request, gauge_groups),
    ]
    for key_fn, ttl, request, groups in plan:
        todo = [g for g in groups if g and not _fresh(cache, key_fn(g), ttl, now)]
        if not todo:
            continue
        try:
            rows = await request([p for g in todo for p in g])
        except FetchError:
            continue
        i = 0
        for g in todo:
            cache.write(key_fn(g), rows[i : i + len(g)], now)
            i += len(g)


def _fresh(cache: FileCache, key: str, ttl: float, now: float) -> bool:
    hit = cache.read(key)
    return hit is not None and now - hit[1] < ttl
