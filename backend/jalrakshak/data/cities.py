"""The 12 JalRakshak cities with SYNTHETIC wards.

Ward names are real neighbourhoods and their coordinates are near the real locality, but the
radius, population, elevation and vulnerability values are synthetic estimates made for this
prototype -- they are NOT official municipal ward data. River gauges are GloFAS grid cells
chosen empirically by ``scripts/find_gauges.py`` and cached in ``gauges.json``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jalrakshak.models import City, EmergencyContact, RiverGauge, Ward

GAUGES_PATH = Path(__file__).with_name("gauges.json")

# (name, lat, lon, radius_m, population, elevation_m, vulnerability)
_WardRow = tuple[str, float, float, int, int, float, float]

# id: (name, state, lat, lon, population, wards)
_CITIES: dict[str, tuple[str, str, float, float, int, list[_WardRow]]] = {
    "mumbai": (
        "Mumbai",
        "Maharashtra",
        19.0760,
        72.8777,
        12_442_000,
        [
            ("Kurla", 19.0726, 72.8845, 1500, 410_000, 6.0, 0.85),
            ("Sion", 19.0390, 72.8619, 1100, 230_000, 5.0, 0.80),
            ("Dharavi", 19.0380, 72.8538, 1000, 600_000, 4.0, 0.95),
            ("Kalina", 19.0760, 72.8640, 1000, 150_000, 7.0, 0.70),
            ("Hindmata", 19.0178, 72.8478, 900, 180_000, 5.0, 0.75),
            ("Andheri East", 19.1136, 72.8697, 1800, 520_000, 11.0, 0.55),
            ("Chembur", 19.0522, 72.9005, 1600, 330_000, 12.0, 0.45),
            ("Malad West", 19.1874, 72.8484, 1700, 480_000, 9.0, 0.50),
        ],
    ),
    "chennai": (
        "Chennai",
        "Tamil Nadu",
        13.0827,
        80.2707,
        7_088_000,
        [
            ("Velachery", 12.9815, 80.2180, 1600, 260_000, 5.0, 0.90),
            ("Pallikaranai", 12.9349, 80.2137, 1500, 120_000, 4.0, 0.90),
            ("Mudichur", 12.9135, 80.0712, 1400, 90_000, 18.0, 0.85),
            ("Saidapet", 13.0213, 80.2231, 1100, 180_000, 7.0, 0.75),
            ("Kotturpuram", 13.0186, 80.2410, 900, 70_000, 6.0, 0.70),
            ("T. Nagar", 13.0418, 80.2341, 1200, 210_000, 9.0, 0.45),
            ("Mylapore", 13.0339, 80.2619, 1100, 160_000, 8.0, 0.40),
            ("Tambaram", 12.9249, 80.1000, 1800, 240_000, 30.0, 0.50),
        ],
    ),
    "guwahati": (
        "Guwahati",
        "Assam",
        26.1445,
        91.7362,
        1_116_000,
        [
            ("Pandu", 26.1720, 91.6800, 1200, 85_000, 50.0, 0.80),
            ("Maligaon", 26.1580, 91.6950, 1200, 95_000, 52.0, 0.60),
            ("Uzan Bazar", 26.1890, 91.7530, 900, 60_000, 49.0, 0.75),
            ("Anil Nagar", 26.1640, 91.7700, 800, 55_000, 47.0, 0.95),
            ("Zoo Road", 26.1690, 91.7780, 1000, 110_000, 48.0, 0.85),
            ("Hatigaon", 26.1330, 91.7950, 1100, 120_000, 51.0, 0.70),
            ("Dispur", 26.1433, 91.7898, 1000, 90_000, 55.0, 0.45),
            ("Beltola", 26.1220, 91.8000, 1300, 130_000, 53.0, 0.65),
        ],
    ),
    "patna": (
        "Patna",
        "Bihar",
        25.5941,
        85.1376,
        2_046_000,
        [
            ("Digha", 25.6450, 85.0900, 1300, 160_000, 49.0, 0.80),
            ("Danapur", 25.6300, 85.0500, 1600, 180_000, 50.0, 0.70),
            ("Patliputra Colony", 25.6250, 85.1000, 900, 70_000, 53.0, 0.40),
            ("Boring Road", 25.6150, 85.1150, 900, 110_000, 53.0, 0.45),
            ("Rajendra Nagar", 25.6080, 85.1600, 1000, 120_000, 48.0, 0.90),
            ("Kankarbagh", 25.5950, 85.1600, 1400, 260_000, 47.0, 0.85),
            ("Gardanibagh", 25.5900, 85.1300, 1000, 130_000, 50.0, 0.60),
            ("Patna City", 25.5930, 85.2300, 1500, 300_000, 51.0, 0.65),
        ],
    ),
    "kochi": (
        "Kochi",
        "Kerala",
        9.9312,
        76.2673,
        2_120_000,
        [
            ("Aluva", 10.1076, 76.3516, 1400, 110_000, 9.0, 0.85),
            ("Eloor", 10.0750, 76.3000, 1000, 40_000, 4.0, 0.80),
            ("Kalamassery", 10.0510, 76.3150, 1300, 75_000, 12.0, 0.55),
            ("Edappally", 10.0261, 76.3086, 1200, 90_000, 6.0, 0.60),
            ("Kakkanad", 10.0159, 76.3419, 1500, 100_000, 15.0, 0.40),
            ("Vyttila", 9.9680, 76.3180, 1000, 85_000, 3.0, 0.75),
            ("Ernakulam South", 9.9700, 76.2900, 1000, 95_000, 3.0, 0.70),
            ("Fort Kochi", 9.9650, 76.2420, 1100, 60_000, 2.0, 0.65),
        ],
    ),
    "srinagar": (
        "Srinagar",
        "Jammu and Kashmir",
        34.0837,
        74.7973,
        1_273_000,
        [
            ("Rajbagh", 34.0705, 74.8235, 900, 45_000, 1584.0, 0.90),
            ("Jawahar Nagar", 34.0680, 74.8115, 800, 40_000, 1585.0, 0.85),
            ("Lal Chowk", 34.0735, 74.8090, 700, 50_000, 1587.0, 0.65),
            ("Batamaloo", 34.0780, 74.7930, 900, 70_000, 1586.0, 0.70),
            ("Bemina", 34.0790, 74.7680, 1200, 80_000, 1583.0, 0.80),
            ("Shivpora", 34.0560, 74.8420, 1000, 45_000, 1590.0, 0.55),
            ("Natipora", 34.0480, 74.7930, 1000, 65_000, 1592.0, 0.40),
            ("Nowhatta", 34.1000, 74.8100, 900, 75_000, 1591.0, 0.45),
        ],
    ),
    "kolkata": (
        "Kolkata",
        "West Bengal",
        22.5726,
        88.3639,
        4_497_000,
        [
            ("Tiljala", 22.5370, 88.3920, 1000, 190_000, 5.0, 0.85),
            ("Kasba", 22.5180, 88.3870, 1100, 170_000, 5.0, 0.75),
            ("Behala", 22.4986, 88.3100, 1600, 350_000, 6.0, 0.80),
            ("Tollygunge", 22.4980, 88.3460, 1300, 260_000, 6.0, 0.70),
            ("Garden Reach", 22.5440, 88.2800, 1200, 220_000, 6.0, 0.85),
            ("Bowbazar", 22.5690, 88.3600, 800, 150_000, 8.0, 0.55),
            ("Shyambazar", 22.6020, 88.3720, 900, 160_000, 8.0, 0.50),
            ("Salt Lake", 22.5800, 88.4150, 1700, 220_000, 7.0, 0.40),
        ],
    ),
    "bhubaneswar": (
        "Bhubaneswar",
        "Odisha",
        20.2961,
        85.8245,
        1_163_000,
        [
            ("Palasuni", 20.3000, 85.8700, 1100, 60_000, 21.0, 0.85),
            ("Rasulgarh", 20.2900, 85.8600, 1000, 80_000, 24.0, 0.70),
            ("Old Town", 20.2370, 85.8370, 1300, 90_000, 30.0, 0.60),
            ("Saheed Nagar", 20.2900, 85.8450, 900, 70_000, 33.0, 0.45),
            ("Nayapalli", 20.2900, 85.8090, 1100, 95_000, 40.0, 0.40),
            ("Chandrasekharpur", 20.3250, 85.8180, 1400, 110_000, 42.0, 0.35),
            ("Patia", 20.3540, 85.8230, 1400, 85_000, 38.0, 0.40),
            ("Khandagiri", 20.2580, 85.7810, 1200, 70_000, 55.0, 0.30),
        ],
    ),
    "surat": (
        "Surat",
        "Gujarat",
        21.1702,
        72.8311,
        6_081_000,
        [
            ("Rander", 21.2190, 72.7920, 1300, 230_000, 9.0, 0.80),
            ("Adajan", 21.1950, 72.7960, 1400, 300_000, 10.0, 0.75),
            ("Katargam", 21.2280, 72.8330, 1300, 350_000, 11.0, 0.70),
            ("Athwalines", 21.1790, 72.8100, 900, 90_000, 12.0, 0.55),
            ("Varachha", 21.2050, 72.8600, 1500, 520_000, 13.0, 0.60),
            ("Udhna", 21.1700, 72.8420, 1300, 330_000, 13.0, 0.55),
            ("Limbayat", 21.1720, 72.8570, 1200, 380_000, 12.0, 0.70),
            ("Piplod", 21.1550, 72.7700, 1200, 120_000, 11.0, 0.40),
        ],
    ),
    "hyderabad": (
        "Hyderabad",
        "Telangana",
        17.3850,
        78.4867,
        10_270_000,
        [
            ("Chaderghat", 17.3800, 78.4900, 800, 90_000, 497.0, 0.85),
            ("Malakpet", 17.3730, 78.5000, 1100, 210_000, 500.0, 0.80),
            ("Amberpet", 17.3920, 78.5150, 1100, 190_000, 505.0, 0.65),
            ("Falaknuma", 17.3300, 78.4700, 1200, 230_000, 520.0, 0.60),
            ("LB Nagar", 17.3460, 78.5520, 1500, 260_000, 482.0, 0.70),
            ("Musheerabad", 17.4170, 78.5000, 1100, 200_000, 515.0, 0.50),
            ("Tolichowki", 17.4000, 78.4150, 1300, 220_000, 530.0, 0.55),
            ("Mehdipatnam", 17.3920, 78.4380, 1100, 180_000, 525.0, 0.45),
        ],
    ),
    "pune": (
        "Pune",
        "Maharashtra",
        18.5204,
        73.8567,
        7_276_000,
        [
            ("Sinhagad Road", 18.4830, 73.8220, 1500, 280_000, 560.0, 0.75),
            ("Kasba Peth", 18.5200, 73.8600, 700, 80_000, 552.0, 0.70),
            ("Sangamwadi", 18.5370, 73.8700, 900, 60_000, 549.0, 0.85),
            ("Shivajinagar", 18.5310, 73.8470, 1100, 150_000, 556.0, 0.55),
            ("Deccan", 18.5150, 73.8410, 900, 110_000, 558.0, 0.60),
            ("Yerawada", 18.5520, 73.8930, 1300, 230_000, 553.0, 0.70),
            ("Kharadi", 18.5510, 73.9400, 1400, 190_000, 562.0, 0.45),
            ("Aundh", 18.5590, 73.8070, 1300, 170_000, 565.0, 0.40),
        ],
    ),
    "dibrugarh": (
        "Dibrugarh",
        "Assam",
        27.4728,
        94.9120,
        154_000,
        [
            ("Mancotta", 27.4700, 94.9300, 1000, 16_000, 104.0, 0.85),
            ("Boiragimoth", 27.4750, 94.9180, 800, 18_000, 105.0, 0.80),
            ("Amolapatty", 27.4830, 94.9120, 700, 14_000, 104.0, 0.90),
            ("Graham Bazar", 27.4850, 94.9050, 700, 15_000, 106.0, 0.70),
            ("Chowkidinghee", 27.4790, 94.9040, 800, 20_000, 107.0, 0.55),
            ("Paltan Bazar", 27.4800, 94.9000, 700, 17_000, 106.0, 0.60),
            ("Jalan Nagar", 27.4780, 94.8950, 900, 22_000, 108.0, 0.50),
            ("Lahowal", 27.4300, 94.8600, 1500, 30_000, 112.0, 0.40),
        ],
    ),
}

#: Main river near each city; used by find_gauges.py and in alert text.
CITY_RIVERS: dict[str, str] = {
    "mumbai": "Mithi",
    "chennai": "Adyar",
    "guwahati": "Brahmaputra",
    "patna": "Ganga",
    "kochi": "Periyar",
    "srinagar": "Jhelum",
    "kolkata": "Hooghly",
    "bhubaneswar": "Mahanadi",
    "surat": "Tapi",
    "hyderabad": "Musi",
    "pune": "Mula-Mutha",
    "dibrugarh": "Brahmaputra",
}

#: National numbers are real; the NDRF number is the published NDRF HQ control room line.
EMERGENCY: list[EmergencyContact] = [
    EmergencyContact(label="National Emergency (police/fire/ambulance)", number="112"),
    EmergencyContact(label="NDMA disaster helpline", number="1078"),
    EmergencyContact(label="State Emergency Operations Centre", number="1070"),
    EmergencyContact(label="Ambulance", number="108"),
    EmergencyContact(label="Fire", number="101"),
    EmergencyContact(label="NDRF control room (New Delhi)", number="+91-11-24363260"),
]


def _load_gauges() -> dict[str, list[RiverGauge]]:
    if not GAUGES_PATH.exists():
        return {}
    raw = json.loads(GAUGES_PATH.read_text(encoding="utf-8"))
    out: dict[str, list[RiverGauge]] = {}
    for city_id, rows in raw.get("gauges", {}).items():
        out[city_id] = [RiverGauge.model_validate(g) for g in rows]
    return out


@lru_cache(maxsize=1)
def all_cities() -> dict[str, City]:
    """Return every city keyed by id (cached, immutable by convention)."""
    gauges = _load_gauges()
    cities: dict[str, City] = {}
    for cid, (name, state, lat, lon, pop, wards) in _CITIES.items():
        cities[cid] = City(
            id=cid,
            name=name,
            state=state,
            lat=lat,
            lon=lon,
            population=pop,
            wards=[
                Ward(
                    id=f"{cid}-w{i + 1:02d}",
                    name=w[0],
                    lat=w[1],
                    lon=w[2],
                    radius_m=w[3],
                    population=w[4],
                    elevation_m=w[5],
                    vulnerability=w[6],
                )
                for i, w in enumerate(wards)
            ],
            gauges=gauges.get(cid, []),
            emergency=list(EMERGENCY),
        )
    return cities


def get_city(city_id: str) -> City | None:
    """Look up a city by id (case-insensitive)."""
    return all_cities().get(city_id.lower())


def city_ids() -> list[str]:
    return list(_CITIES)
