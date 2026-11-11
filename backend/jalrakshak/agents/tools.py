"""Typed tools the agents (LLM or rules policy) can call.

Every tool has a JSON schema (sent to the LLM) and an async handler operating on a
``ToolContext`` that holds ONE CityRisk snapshot per run, so every agent sees the same facts.
Arguments are validated before execution; invalid calls raise ``ToolArgError``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from jalrakshak.adapters import osrm
from jalrakshak.adapters.osrm import haversine_m
from jalrakshak.agents.facts import Facts, build_facts, dominant_gauge
from jalrakshak.data.facilities import get_facility
from jalrakshak.evacuation import suitable_facilities
from jalrakshak.models import City, CityRisk, EvacuationPlan, RiskLevel

Handler = Callable[[dict[str, Any], "ToolContext"], Awaitable[Any]]


class ToolArgError(ValueError):
    pass


@dataclass
class ToolContext:
    city: City
    risk: CityRisk
    now: datetime
    facts: Facts | None = None
    plans: list[EvacuationPlan] = field(default_factory=list)
    alert_draft: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # decision, alert status, provider...

    def get_facts(self) -> Facts:
        if self.facts is None:
            self.facts = build_facts(self.risk)
        return self.facts


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "array": (list,),
    "object": (dict,),
    "boolean": (bool,),
}


def validate_args(schema: dict[str, Any], args: Any) -> dict[str, Any]:
    """Minimal JSON-schema check (required, types, enums); numbers given as strings are coerced."""
    if not isinstance(args, dict):
        raise ToolArgError("arguments must be an object")
    props: dict[str, Any] = schema.get("properties", {})
    out = dict(args)
    for req in schema.get("required", []):
        if req not in out or out[req] in (None, ""):
            raise ToolArgError(f"missing required argument '{req}'")
    for key, val in list(out.items()):
        if key not in props:
            del out[key]  # ignore hallucinated extra args
            continue
        typ = props[key].get("type")
        if typ in ("number", "integer") and isinstance(val, str):
            try:
                val = float(val) if typ == "number" else int(val)
            except ValueError as exc:
                raise ToolArgError(f"'{key}' must be a {typ}") from exc
            out[key] = val
        if (typ and not isinstance(val, _TYPES[typ])) or (
            isinstance(val, bool) and typ in ("number", "integer")
        ):
            raise ToolArgError(f"'{key}' must be a {typ}")
        if "enum" in props[key] and val not in props[key]["enum"]:
            raise ToolArgError(f"'{key}' must be one of {props[key]['enum']}")
    return out


def _check_city(args: dict[str, Any], ctx: ToolContext) -> None:
    cid = str(args.get("city_id", ctx.city.id)).lower().strip()
    if cid not in (ctx.city.id, ctx.city.name.lower()):
        raise ToolArgError(f"only city_id '{ctx.city.id}' is in scope for this run")


# ---------------------------------------------------------------- handlers


async def _get_city_risk(args: dict[str, Any], ctx: ToolContext) -> Any:
    _check_city(args, ctx)
    r = ctx.risk
    peak = max(r.horizon, key=lambda p: p.score) if r.horizon else None
    return {
        "city": r.city.name,
        "level": r.overall.level,
        "score": r.overall.score,
        "explanation": r.overall.explanation,
        "peak_time_utc": peak.t if peak else None,
        "peak_score": peak.score if peak else None,
        "rain_max_24h_mm": r.overall.factors.rain_24h_mm,
        "rain_72h_mm": r.overall.factors.rain_72h_mm,
        "antecedent_7d_mm": r.overall.factors.antecedent_7d_mm,
        "has_river_gauge": bool(r.gauges),
        "stale": r.stale,
    }


async def _get_ward_risks(args: dict[str, Any], ctx: ToolContext) -> Any:
    _check_city(args, ctx)
    top_n = int(args.get("top_n", 5))
    wards = {w.id: w for w in ctx.city.wards}
    ranked = sorted(ctx.risk.wards, key=lambda w: -w.risk.score)[: max(1, min(top_n, 10))]
    return [
        {
            "ward_id": w.ward_id,
            "name": wards[w.ward_id].name,
            "score": w.risk.score,
            "level": w.risk.level,
            "population": wards[w.ward_id].population,
            "vulnerability": wards[w.ward_id].vulnerability,
            "lat": wards[w.ward_id].lat,
            "lon": wards[w.ward_id].lon,
        }
        for w in ranked
    ]


async def _get_gauge_status(args: dict[str, Any], ctx: ToolContext) -> Any:
    _check_city(args, ctx)
    if not ctx.risk.gauges:
        return {"gauges": [], "note": "no meaningful GloFAS river cell; risk is rainfall-driven"}
    dom = dominant_gauge(ctx.risk)
    return {
        "gauges": [
            {
                "river": g.gauge.river,
                "current_m3s": g.current_m3s,
                "peak_m3s_next_72h": g.peak_m3s,
                "peak_date": g.peak_date,
                "status": g.status,
                "warning_m3s": g.gauge.warning_m3s,
                "danger_m3s": g.gauge.danger_m3s,
                "extreme_m3s": g.gauge.extreme_m3s,
                "peak_pct_of_danger": round(100 * g.peak_m3s / g.gauge.danger_m3s),
                "dominant": g is dom,
            }
            for g in ctx.risk.gauges
        ]
    }


async def _find_shelters(args: dict[str, Any], ctx: ToolContext) -> Any:
    lat, lon = float(args["lat"]), float(args["lon"])
    k = int(args.get("k", 3))
    fs = suitable_facilities(ctx.city, lat, lon, k=max(1, min(k, 5)))
    return [
        {
            "facility_id": f.id,
            "name": f.name,
            "type": f.type,
            "distance_m": round(haversine_m(lat, lon, f.lat, f.lon)),
            "free_places": f.capacity - f.occupancy,
            "elevation_m": f.elevation_m,
        }
        for f in fs
    ]


async def _plan_route(args: dict[str, Any], ctx: ToolContext) -> Any:
    origin = args["origin"]
    if not isinstance(origin, dict) or "lat" not in origin or "lon" not in origin:
        raise ToolArgError("origin must be {lat, lon}")
    fac = get_facility(str(args["facility_id"]))
    if fac is None or fac.city_id != ctx.city.id:
        raise ToolArgError(f"unknown facility_id '{args['facility_id']}'")
    r = await osrm.route((float(origin["lat"]), float(origin["lon"])), (fac.lat, fac.lon))
    return {
        "facility_id": fac.id,
        "method": r.method,
        "distance_m": r.distance_m,
        "duration_min": round(r.duration_s / 60),
        "points": len(r.geometry),
    }


async def _draft_alert(args: dict[str, Any], ctx: ToolContext) -> Any:
    from jalrakshak.agents.templates import render_all

    facts = ctx.get_facts()
    level: RiskLevel = args.get("level") or facts.level
    if level != facts.level:
        raise ToolArgError(f"level must match the verified level '{facts.level}'")
    versions = render_all(facts)
    ctx.alert_draft = {"level": level, "versions": versions}
    return {
        "verified_facts": facts.as_dict(),
        "template_en": versions["en"],
        "note": "Hindi, Marathi, Tamil and Bengali versions are produced from vetted templates.",
    }


async def _get_emergency_contacts(args: dict[str, Any], ctx: ToolContext) -> Any:
    _check_city(args, ctx)
    return [c.model_dump() for c in ctx.city.emergency]


async def _compose_sitrep_section(args: dict[str, Any], ctx: ToolContext) -> Any:
    from jalrakshak.agents.sitrep import SECTION_HEADINGS, compose_section

    heading = str(args["heading"])
    if heading not in SECTION_HEADINGS:
        raise ToolArgError(f"heading must be one of {SECTION_HEADINGS}")
    return {"heading": heading, "body": compose_section(heading, ctx)}


_CITY = {"city_id": {"type": "string", "description": "City id, e.g. 'guwahati'"}}

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "get_city_risk",
            "Overall flood risk for the city now (score 0-100, level, explanation, horizon peak).",
            {"type": "object", "properties": _CITY, "required": ["city_id"]},
            _get_city_risk,
        ),
        Tool(
            "get_ward_risks",
            "Highest-risk wards of the city with score, level, population and coordinates.",
            {
                "type": "object",
                "properties": {
                    **_CITY,
                    "top_n": {"type": "integer", "description": "How many (1-10)"},
                },
                "required": ["city_id"],
            },
            _get_ward_risks,
        ),
        Tool(
            "get_gauge_status",
            "GloFAS river discharge vs warning/danger/extreme thresholds for the city's river.",
            {"type": "object", "properties": _CITY, "required": ["city_id"]},
            _get_gauge_status,
        ),
        Tool(
            "find_shelters",
            "Nearest suitable shelters/relief camps (higher ground, free capacity) to a point.",
            {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "k": {"type": "integer", "description": "How many (1-5)"},
                },
                "required": ["lat", "lon"],
            },
            _find_shelters,
        ),
        Tool(
            "plan_route",
            "Walking route from an origin to a facility (OSRM, straight-line fallback).",
            {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "object",
                        "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}},
                    },
                    "facility_id": {"type": "string"},
                },
                "required": ["origin", "facility_id"],
            },
            _plan_route,
        ),
        Tool(
            "draft_alert",
            "Get the verified fact sheet and the vetted English template for the public alert.",
            {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["green", "yellow", "orange", "red"]},
                    "wards": {"type": "array", "items": {"type": "string"}},
                    "key_facts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["level"],
            },
            _draft_alert,
        ),
        Tool(
            "get_emergency_contacts",
            "Emergency helpline numbers for the city.",
            {"type": "object", "properties": _CITY, "required": ["city_id"]},
            _get_emergency_contacts,
        ),
        Tool(
            "compose_sitrep_section",
            "Deterministic body text for one situation-report section.",
            {
                "type": "object",
                "properties": {"heading": {"type": "string"}},
                "required": ["heading"],
            },
            _compose_sitrep_section,
        ),
    ]
}


def specs(names: list[str]) -> list[dict[str, Any]]:
    return [TOOLS[n].spec() for n in names]


async def call_tool(name: str, args: Any, ctx: ToolContext) -> Any:
    """Validate and execute a tool. Raises ToolArgError for unknown tools or bad args."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolArgError(f"unknown tool '{name}'")
    return await tool.handler(validate_args(tool.parameters, args), ctx)
