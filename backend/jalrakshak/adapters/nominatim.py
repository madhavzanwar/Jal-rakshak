"""Nominatim geocoder (OpenStreetMap), India only, cached for 30 days.

Respects the usage policy: custom User-Agent and at most one request per second
(process-wide lock).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from jalrakshak.adapters.cache import FileCache
from jalrakshak.adapters.http import get_json
from jalrakshak.models import GeocodeResult

SEARCH_URL = "https://nominatim.openstreetmap.org/search"
TTL_S = 30 * 24 * 3600
MIN_INTERVAL_S = 1.1

_locks: dict[int, asyncio.Lock] = {}
_last_call = 0.0


def _lock() -> asyncio.Lock:
    """One lock per event loop (tests and scripts may run several loops)."""
    loop_id = id(asyncio.get_running_loop())
    return _locks.setdefault(loop_id, asyncio.Lock())


async def _throttled_search(q: str, limit: int) -> Any:
    global _last_call
    async with _lock():
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await get_json(
                SEARCH_URL,
                {"q": q, "format": "jsonv2", "countrycodes": "in", "limit": limit},
                timeout=15.0,
                retries=1,
            )
        finally:
            _last_call = time.monotonic()


async def geocode(q: str, limit: int = 5, cache: FileCache | None = None) -> list[GeocodeResult]:
    """Geocode a free-text query within India. Raises FetchError if offline and uncached."""
    norm = " ".join(q.lower().split())
    if not norm:
        return []

    async def fetch() -> Any:
        rows = await _throttled_search(norm, limit)
        return [
            {"display_name": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
            for r in rows
        ]

    res = await (cache or FileCache()).get_or_fetch(f"geocode:{norm}:{limit}", TTL_S, fetch)
    return [GeocodeResult.model_validate(r) for r in res.value]
