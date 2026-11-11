"""Deterministic SYNTHETIC shelters, hospitals and relief camps (8-12 per city).

Facilities are placed a few hundred metres from a ward centroid on slightly higher ground
(ward elevation + 3..15 m). Names are plausible but invented and phone numbers are clearly
fake (``+91-00000-xxxxx``). Generation is seeded per city so ids are stable across runs.
Run ``python -m jalrakshak.data.facilities`` to refresh ``facilities.json``.
"""

from __future__ import annotations

import json
import math
import random
import zlib
from functools import lru_cache
from pathlib import Path

from jalrakshak.data.cities import all_cities
from jalrakshak.models import City, Facility, FacilityType

FACILITIES_PATH = Path(__file__).with_name("facilities.json")

_NAMES: dict[FacilityType, list[str]] = {
    "shelter": [
        "Govt. Higher Secondary School Shelter",
        "Municipal Community Hall Shelter",
        "Govt. Primary School Shelter",
        "Kendriya Vidyalaya Flood Shelter",
        "Multipurpose Flood Shelter",
        "Panchayat Bhawan Shelter",
    ],
    "hospital": [
        "District Civil Hospital",
        "Urban Primary Health Centre",
        "Community Health Centre",
        "ESI Hospital",
    ],
    "relief_camp": [
        "Relief Camp - Stadium Grounds",
        "Relief Camp - Govt. College Campus",
        "SDRF/NDRF Staging & Relief Camp",
        "Relief Camp - Exhibition Grounds",
    ],
}

_CAPACITY: dict[FacilityType, tuple[int, int]] = {
    "shelter": (250, 1500),
    "hospital": (60, 400),
    "relief_camp": (600, 3000),
}


def _type_plan(n: int) -> list[FacilityType]:
    """About half shelters, a quarter hospitals, a quarter relief camps."""
    n_hosp = max(2, n // 4)
    n_camp = max(2, n // 4)
    n_shel = n - n_hosp - n_camp
    return ["shelter"] * n_shel + ["hospital"] * n_hosp + ["relief_camp"] * n_camp


def generate_city_facilities(city: City) -> list[Facility]:
    """Deterministically generate the facilities for one city."""
    rng = random.Random(zlib.crc32(city.id.encode()))
    n = rng.randint(8, 12)
    # Safer (low-vulnerability) wards first so shelters sit on better ground, then cycle.
    wards = sorted(city.wards, key=lambda w: w.vulnerability)
    used_names: set[str] = set()
    out: list[Facility] = []
    for i, ftype in enumerate(_type_plan(n)):
        ward = wards[i % len(wards)]
        base = rng.choice(_NAMES[ftype])
        name = f"{base}, {ward.name}"
        k = 2
        while name in used_names:
            name = f"{base} No. {k}, {ward.name}"
            k += 1
        used_names.add(name)
        dist_m = rng.uniform(250, 900)
        bearing = rng.uniform(0, 2 * math.pi)
        dlat = dist_m * math.cos(bearing) / 111_320
        dlon = dist_m * math.sin(bearing) / (111_320 * math.cos(math.radians(ward.lat)))
        lo, hi = _CAPACITY[ftype]
        capacity = rng.randrange(lo, hi, 10)
        out.append(
            Facility(
                id=f"{city.id}-f{i + 1:02d}",
                city_id=city.id,
                ward_id=ward.id,
                name=name,
                type=ftype,
                lat=round(ward.lat + dlat, 5),
                lon=round(ward.lon + dlon, 5),
                capacity=capacity,
                occupancy=int(capacity * rng.uniform(0.0, 0.3)),
                phone=f"+91-00000-{rng.randint(10000, 99999)}",
                elevation_m=round(ward.elevation_m + rng.uniform(3, 15), 1),
            )
        )
    return out


@lru_cache(maxsize=1)
def all_facilities() -> dict[str, list[Facility]]:
    """Facilities for every city keyed by city id."""
    return {cid: generate_city_facilities(c) for cid, c in all_cities().items()}


def city_facilities(city_id: str) -> list[Facility]:
    return all_facilities().get(city_id, [])


def get_facility(facility_id: str) -> Facility | None:
    city_id = facility_id.rsplit("-f", 1)[0]
    return next((f for f in city_facilities(city_id) if f.id == facility_id), None)


def write_json(path: Path = FACILITIES_PATH) -> None:
    data = {cid: [f.model_dump() for f in fs] for cid, fs in all_facilities().items()}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_json()
    print(f"wrote {FACILITIES_PATH} ({sum(len(v) for v in all_facilities().values())} facilities)")
