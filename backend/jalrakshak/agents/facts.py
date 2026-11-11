"""Verified fact sheet derived from one CityRisk snapshot.

Agents may only state facts from this sheet: the alert guards check that every number in a
drafted message exists in ``allowed_numbers()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from jalrakshak.data.cities import CITY_RIVERS
from jalrakshak.models import CityRisk, Facility, GaugeReading, RiskLevel, Ward
from jalrakshak.risk.series import parse_ts
from jalrakshak.risk.thresholds import imd_category, level_rank

IST = timedelta(hours=5, minutes=30)
EMERGENCY_NUMBERS = ("112", "1078", "1070", "108", "101")
WINDOW_NUMBERS = ("3", "6", "12", "24", "48", "72", "100")  # windows (h) and score scale


@dataclass
class WardFact:
    id: str
    name: str
    score: float
    level: RiskLevel
    population: int
    vulnerability: float


@dataclass
class Facts:
    city_id: str
    city: str
    state: str
    level: RiskLevel
    score: float
    explanation: str
    river: str
    has_gauge: bool
    gauge_status: str
    gauge_pct_of_danger: int
    gauge_peak_m3s: int
    gauge_peak_date: str
    rain_24h_mm: int
    rain_72h_mm: int
    max_intensity_mmph: int
    antecedent_7d_mm: int
    peak_time_ist: str  # "HH:MM IST, DD Mon"
    peak_hhmm: str
    wards: list[WardFact]  # target wards, highest risk first
    population_at_risk: int
    shelter: str = ""
    shelter_phone: str = ""
    extra_numbers: set[str] = field(default_factory=set)

    @property
    def ward_names(self) -> list[str]:
        return [w.name for w in self.wards]

    @property
    def rain_category(self) -> str:
        return imd_category(self.rain_24h_mm)

    def as_dict(self) -> dict[str, object]:
        return {
            "city": self.city,
            "state": self.state,
            "level": self.level,
            "score": self.score,
            "river": self.river if self.has_gauge else None,
            "river_status": self.gauge_status if self.has_gauge else None,
            "river_peak_pct_of_danger": self.gauge_pct_of_danger if self.has_gauge else None,
            "rain_max_24h_mm": self.rain_24h_mm,
            "rain_category": self.rain_category,
            "rain_72h_mm": self.rain_72h_mm,
            "max_intensity_mmph": self.max_intensity_mmph,
            "antecedent_7d_mm": self.antecedent_7d_mm,
            "peak_time": self.peak_time_ist,
            "target_wards": self.ward_names,
            "population_at_risk": self.population_at_risk,
            "nearest_shelter": self.shelter or None,
            "emergency_number": "112",
        }

    def allowed_numbers(self) -> set[str]:
        """Every number a message may contain (normalised strings)."""
        nums: set[str] = set(EMERGENCY_NUMBERS) | set(WINDOW_NUMBERS) | self.extra_numbers
        for v in (
            self.score,
            self.gauge_pct_of_danger,
            self.gauge_peak_m3s,
            self.rain_24h_mm,
            self.rain_72h_mm,
            self.max_intensity_mmph,
            self.antecedent_7d_mm,
            self.population_at_risk,
            len(self.wards),
        ):
            nums |= _num_forms(float(v))
        for text in (
            self.peak_time_ist,
            self.gauge_peak_date,
            self.shelter,
            self.shelter_phone,
            *self.ward_names,
            self.city,
        ):
            nums |= set(re.findall(r"\d+", text))
        return nums


def _num_forms(v: float) -> set[str]:
    out = {str(round(v)), f"{v:.1f}", f"{v:,.0f}"}
    if v == int(v):
        out.add(str(int(v)))
    return out


def fmt_ist(ts: str) -> tuple[str, str]:
    """('18:00 IST, 02 Jul', '18:00') for a UTC ISO timestamp."""
    dt = parse_ts(ts) + IST
    return dt.strftime("%H:%M IST, %d %b"), dt.strftime("%H:%M")


def dominant_gauge(risk: CityRisk) -> GaugeReading | None:
    if not risk.gauges:
        return None
    return max(risk.gauges, key=lambda g: g.peak_m3s / max(g.gauge.danger_m3s, 1e-9))


def target_wards(risk: CityRisk, max_n: int = 4) -> list[Ward]:
    """Wards at the city's alert level or one below (>= yellow), highest score first."""
    ward_map = {w.id: w for w in risk.city.wards}
    ranked = sorted(risk.wards, key=lambda w: -w.risk.score)
    floor = max(1, level_rank(risk.overall.level) - 1)
    picked = [ward_map[w.ward_id] for w in ranked if level_rank(w.risk.level) >= floor]
    return (picked or [ward_map[ranked[0].ward_id]])[:max_n]


def build_facts(risk: CityRisk, shelter: Facility | None = None, max_wards: int = 4) -> Facts:
    """Distil a CityRisk snapshot into the verified fact sheet."""
    o = risk.overall
    g = dominant_gauge(risk)
    peak = max(risk.horizon, key=lambda p: p.score).t if risk.horizon else risk.generated_at
    peak_ist, peak_hhmm = fmt_ist(peak)
    wards = target_wards(risk, max_wards)
    scores = {w.ward_id: w.risk for w in risk.wards}
    return Facts(
        city_id=risk.city.id,
        city=risk.city.name,
        state=risk.city.state,
        level=o.level,
        score=o.score,
        explanation=o.explanation,
        river=g.gauge.river if g else CITY_RIVERS.get(risk.city.id, ""),
        has_gauge=g is not None,
        gauge_status=g.status if g else "n/a",
        gauge_pct_of_danger=round(100 * g.peak_m3s / g.gauge.danger_m3s) if g else 0,
        gauge_peak_m3s=round(g.peak_m3s) if g else 0,
        gauge_peak_date=g.peak_date if g else "",
        rain_24h_mm=round(o.factors.rain_24h_mm),
        rain_72h_mm=round(o.factors.rain_72h_mm),
        max_intensity_mmph=round(o.factors.max_intensity_mmph),
        antecedent_7d_mm=round(o.factors.antecedent_7d_mm),
        peak_time_ist=peak_ist,
        peak_hhmm=peak_hhmm,
        wards=[
            WardFact(
                w.id, w.name, scores[w.id].score, scores[w.id].level, w.population, w.vulnerability
            )
            for w in wards
        ],
        population_at_risk=sum(w.population for w in wards),
        shelter=shelter.name if shelter else "",
        shelter_phone=shelter.phone if shelter else "",
    )
