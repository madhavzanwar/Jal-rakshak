"""Pydantic v2 models mirroring ``docs/CONTRACT.md`` exactly (snake_case JSON).

Every API response and the demo scenario file are serialised from these models, so the
frontend's zod schemas and the backend can never drift apart silently.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["green", "yellow", "orange", "red"]
Lang = Literal["en", "hi", "mr", "ta", "bn"]
AgentName = Literal["monitor", "alert_drafter", "evacuation_planner", "sitrep"]
StepKind = Literal["thought", "tool_call", "tool_result", "decision", "guard", "final", "error"]
AlertStatus = Literal["pending_approval", "approved", "rejected", "sent"]
FacilityType = Literal["shelter", "hospital", "relief_camp"]
RouteMethod = Literal["osrm", "straight_line"]
GaugeStatus = Literal["normal", "warning", "danger", "extreme"]
Trigger = Literal["manual", "scheduled", "demo"]
Channel = Literal["sms", "whatsapp"]

LANGS: tuple[Lang, ...] = ("en", "hi", "mr", "ta", "bn")
LEVELS: tuple[RiskLevel, ...] = ("green", "yellow", "orange", "red")


class _Model(BaseModel):
    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------- core entities


class Ward(_Model):
    """Synthetic but plausible ward/zone, drawn as a circle on the map."""

    id: str
    name: str
    lat: float
    lon: float
    radius_m: float
    population: int
    elevation_m: float
    vulnerability: float = Field(ge=0, le=1)


class RiverGauge(_Model):
    """A GloFAS grid cell representing the main river near a city."""

    id: str
    river: str
    lat: float
    lon: float
    warning_m3s: float
    danger_m3s: float
    extreme_m3s: float


class EmergencyContact(_Model):
    label: str
    number: str


class City(_Model):
    id: str
    name: str
    state: str
    lat: float
    lon: float
    population: int
    wards: list[Ward]
    gauges: list[RiverGauge]
    emergency: list[EmergencyContact]


class RiskComponents(_Model):
    rain: float
    river: float
    antecedent: float
    vulnerability: float


class RiskFactors(_Model):
    """Raw inputs plus the normalised 0..1 components of the risk score."""

    rain_24h_mm: float
    rain_72h_mm: float
    max_intensity_mmph: float
    antecedent_7d_mm: float
    discharge_ratio: float
    vulnerability: float
    components: RiskComponents


class RiskScore(_Model):
    score: float
    level: RiskLevel
    factors: RiskFactors
    explanation: str
    ml_probability: float | None = None


class CitySummary(_Model):
    city: City
    risk: RiskScore
    peak_time: str | None
    stale: bool
    updated_at: str


class HorizonPoint(_Model):
    t: str
    score: float
    level: RiskLevel


class RainPoint(_Model):
    t: str
    mm: float


class DischargePoint(_Model):
    date: str
    m3s: float


class GaugeReading(_Model):
    gauge: RiverGauge
    series: list[DischargePoint]
    current_m3s: float
    peak_m3s: float
    peak_date: str
    status: GaugeStatus


class WardRisk(_Model):
    ward_id: str
    risk: RiskScore


class SourceStatus(_Model):
    name: str
    url: str
    ok: bool
    fetched_at: str | None


class CityRisk(_Model):
    city: City
    generated_at: str
    stale: bool
    data_age_minutes: float
    sources: list[SourceStatus]
    overall: RiskScore
    horizon: list[HorizonPoint]
    rainfall: list[RainPoint]
    gauges: list[GaugeReading]
    wards: list[WardRisk]


class Facility(_Model):
    id: str
    city_id: str
    ward_id: str
    name: str
    type: FacilityType
    lat: float
    lon: float
    capacity: int
    occupancy: int
    phone: str
    elevation_m: float


class Route(_Model):
    method: RouteMethod
    distance_m: float
    duration_s: float
    geometry: list[tuple[float, float]]


class LatLon(_Model):
    lat: float
    lon: float


class FacilityRoute(_Model):
    facility: Facility
    route: Route


class EvacuationPlan(_Model):
    origin: LatLon
    facility: Facility
    route: Route
    alternatives: list[FacilityRoute]
    notes: list[str]


class Advice(_Model):
    now: list[str]
    prepare: list[str]
    avoid: list[str]


class PointRisk(_Model):
    lat: float
    lon: float
    city: City
    ward: Ward
    distance_to_city_km: float
    risk: RiskScore
    advice: Advice
    evacuation: EvacuationPlan
    emergency: list[EmergencyContact]
    stale: bool


class GeocodeResult(_Model):
    display_name: str
    lat: float
    lon: float


# ---------------------------------------------------------------- agents


class AgentStep(_Model):
    id: str
    run_id: str
    seq: int
    agent: AgentName
    kind: StepKind
    ts: str
    content: str
    tool: str | None = None
    input: Any | None = None
    output: Any | None = None
    duration_ms: float = 0.0


class AlertVersion(_Model):
    lang: Lang
    sms: str
    whatsapp: str


class GuardResult(_Model):
    name: str
    passed: bool
    detail: str


class DispatchLogEntry(_Model):
    ts: str
    channel: Channel
    lang: Lang
    recipients_estimate: int
    simulated: Literal[True] = True


class Alert(_Model):
    id: str
    run_id: str
    city_id: str
    level: RiskLevel
    status: AlertStatus
    created_at: str
    target_wards: list[str]
    versions: list[AlertVersion]
    guards: list[GuardResult]
    edited: bool = False
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    dispatch_log: list[DispatchLogEntry] = Field(default_factory=list)


class SitRepSection(_Model):
    heading: str
    body: str


class KeyFigure(_Model):
    label: str
    value: str


class SitRep(_Model):
    run_id: str
    city_id: str
    generated_at: str
    title: str
    summary: str
    sections: list[SitRepSection]
    key_figures: list[KeyFigure]


class LLMInfo(_Model):
    provider: str
    model: str


class Decision(_Model):
    should_alert: bool
    level: RiskLevel
    reason: str


class AgentRun(_Model):
    id: str
    city_id: str
    trigger: Trigger
    started_at: str
    finished_at: str | None
    llm: LLMInfo
    decision: Decision
    steps: list[AgentStep]
    alert_id: str | None
    evacuation: list[EvacuationPlan]
    sitrep: SitRep | None


# ---------------------------------------------------------------- API bodies / misc


class HealthLLM(_Model):
    provider: str
    model: str
    available: bool


class Health(_Model):
    status: Literal["ok"] = "ok"
    version: str
    llm: HealthLLM
    demo: bool


class EvacuationRequest(_Model):
    lat: float
    lon: float
    city_id: str | None = None


class AgentRunRequest(_Model):
    city_id: str
    trigger: Trigger = "manual"


class AlertEditRequest(_Model):
    versions: list[AlertVersion]
    reviewer: str


class ApproveRequest(_Model):
    reviewer: str


class RejectRequest(_Model):
    reviewer: str
    reason: str = ""


class DemoFrame(_Model):
    index: int
    t: str
    caption: str
    cities: list[CitySummary]
    details: dict[str, CityRisk]


class RecordedWith(_Model):
    provider: str
    model: str
    recorded_at: str


class FrameRun(_Model):
    frame: int
    run: AgentRun


class DemoScenario(_Model):
    id: Literal["assam-2026-replay"] = "assam-2026-replay"
    title: str
    description: str
    recorded_with: RecordedWith
    frames: list[DemoFrame]
    facilities: dict[str, list[Facility]]
    agent_runs: list[FrameRun]
    alerts: list[Alert]
    geocode: dict[str, list[GeocodeResult]]
