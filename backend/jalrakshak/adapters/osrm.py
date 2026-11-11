"""Routing via the public OSRM demo server with a straight-line fallback.

The public demo server only hosts the car profile (the ``foot`` path is served by the same
graph), so for walking evacuation we keep OSRM's road geometry and distance but recompute the
duration at walking speed. If OSRM fails, a haversine straight line at 4 km/h is returned
(``method="straight_line"``).
"""

from __future__ import annotations

import math
from typing import Any, Literal

from jalrakshak.adapters.cache import FileCache
from jalrakshak.adapters.http import get_json
from jalrakshak.models import Route

OSRM_URL = "https://router.project-osrm.org/route/v1"
TTL_S = 24 * 3600
WALK_MPS = 4000 / 3600  # 4 km/h, conservative for flooded streets
Mode = Literal["walk", "drive"]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def straight_line(origin: tuple[float, float], dest: tuple[float, float]) -> Route:
    """Fallback route: a straight line walked at 4 km/h."""
    d = haversine_m(*origin, *dest)
    return Route(
        method="straight_line",
        distance_m=round(d, 1),
        duration_s=round(d / WALK_MPS, 1),
        geometry=[
            (round(origin[0], 5), round(origin[1], 5)),
            (round(dest[0], 5), round(dest[1], 5)),
        ],
    )


async def route(
    origin: tuple[float, float],
    dest: tuple[float, float],
    mode: Mode = "walk",
    cache: FileCache | None = None,
) -> Route:
    """Road route from ``origin`` to ``dest`` (both ``(lat, lon)``); never raises."""
    profile = "foot" if mode == "walk" else "driving"
    coords = f"{origin[1]:.5f},{origin[0]:.5f};{dest[1]:.5f},{dest[0]:.5f}"

    async def fetch() -> Any:
        data = await get_json(
            f"{OSRM_URL}/{profile}/{coords}",
            {"overview": "simplified", "geometries": "geojson"},
            timeout=10.0,
            retries=1,
        )
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM: {data.get('code')}")
        r = data["routes"][0]
        return {
            "distance_m": float(r["distance"]),
            "duration_s": float(r["duration"]),
            "geometry": [[round(c[1], 5), round(c[0], 5)] for c in r["geometry"]["coordinates"]],
        }

    try:
        res = await (cache or FileCache()).get_or_fetch(f"osrm:{profile}:{coords}", TTL_S, fetch)
    except Exception:
        return straight_line(origin, dest)
    v = res.value
    duration = v["distance_m"] / WALK_MPS if mode == "walk" else v["duration_s"]
    return Route(
        method="osrm",
        distance_m=round(v["distance_m"], 1),
        duration_s=round(duration, 1),
        geometry=[(g[0], g[1]) for g in v["geometry"]],
    )
