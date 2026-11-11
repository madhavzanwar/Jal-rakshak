"""Evacuation planning core: pick suitable nearby facilities and route to them.

Suitable = shelter or relief camp with free capacity (occupancy < 90 %) on ground at least as
high as the origin ward. The three nearest by haversine are routed (OSRM with straight-line
fallback); the quickest becomes the primary plan and the others are alternatives.
"""

from __future__ import annotations

import asyncio

from jalrakshak.adapters import osrm
from jalrakshak.adapters.osrm import haversine_m
from jalrakshak.data.facilities import city_facilities
from jalrakshak.models import City, EvacuationPlan, Facility, FacilityRoute, LatLon, Route, Ward

MAX_OCCUPANCY = 0.9


def nearest_ward(city: City, lat: float, lon: float) -> Ward:
    return min(city.wards, key=lambda w: haversine_m(lat, lon, w.lat, w.lon))


def suitable_facilities(
    city: City, lat: float, lon: float, k: int = 3, min_elevation_m: float | None = None
) -> list[Facility]:
    """The ``k`` nearest evacuation facilities passing elevation/capacity filters."""
    if min_elevation_m is None:
        min_elevation_m = nearest_ward(city, lat, lon).elevation_m
    pool = [f for f in city_facilities(city.id) if f.type in ("shelter", "relief_camp")]
    ok = [
        f
        for f in pool
        if f.elevation_m >= min_elevation_m and f.occupancy < MAX_OCCUPANCY * f.capacity
    ]
    candidates = ok or pool
    return sorted(candidates, key=lambda f: haversine_m(lat, lon, f.lat, f.lon))[:k]


def _notes(primary: FacilityRoute, origin_ward: Ward) -> list[str]:
    f, r = primary.facility, primary.route
    notes = [
        f"Nearest suitable {f.type.replace('_', ' ')}: {f.name} "
        f"({r.distance_m / 1000:.1f} km, about {r.duration_s / 60:.0f} min on foot).",
        f"Free places: {max(f.capacity - f.occupancy, 0)} of {f.capacity}; "
        f"site is {f.elevation_m - origin_ward.elevation_m:+.0f} m relative to {origin_ward.name}.",
    ]
    if r.method == "straight_line":
        notes.append(
            "Road routing unavailable: straight-line distance shown. Follow official directions "
            "and avoid flooded roads."
        )
    else:
        notes.append("Route from the OSRM road network; avoid any stretch that is under water.")
    notes.append("Facilities and capacities are synthetic demo data; call 112 in an emergency.")
    return notes


async def plan_evacuation(city: City, lat: float, lon: float) -> EvacuationPlan:
    """Evacuation plan from ``(lat, lon)`` to the quickest of the 3 nearest suitable sites."""
    ward = nearest_ward(city, lat, lon)
    facilities = suitable_facilities(city, lat, lon, k=3, min_elevation_m=ward.elevation_m)
    routes: list[Route] = await asyncio.gather(
        *(osrm.route((lat, lon), (f.lat, f.lon)) for f in facilities)
    )
    pairs = sorted(
        (FacilityRoute(facility=f, route=r) for f, r in zip(facilities, routes, strict=True)),
        key=lambda p: p.route.duration_s,
    )
    primary = pairs[0]
    return EvacuationPlan(
        origin=LatLon(lat=round(lat, 5), lon=round(lon, 5)),
        facility=primary.facility,
        route=primary.route,
        alternatives=pairs[1:3],
        notes=_notes(primary, ward),
    )
