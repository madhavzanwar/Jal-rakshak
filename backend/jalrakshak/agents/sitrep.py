"""Sitrep agent: a district-officer situation report.

Sections are composed deterministically from the run's facts (via the
``compose_sitrep_section`` tool, logged as steps). The LLM writes only the short summary
paragraph, constrained to the verified facts; the summary is guard-checked (numbers must be
verified, no links, length) and replaced by a deterministic summary if it fails.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from jalrakshak.agents.facts import Facts, dominant_gauge
from jalrakshak.agents.guards import URL_RE, unverified_numbers
from jalrakshak.agents.llm import LLMError, LLMProvider, Message, RulesProvider
from jalrakshak.agents.react import StepRecorder
from jalrakshak.agents.tools import ToolContext, call_tool
from jalrakshak.models import AgentName, KeyFigure, SitRep, SitRepSection
from jalrakshak.risk.series import fmt_ts

AGENT: AgentName = "sitrep"
SECTION_HEADINGS = (
    "Situation",
    "River & Rainfall Outlook",
    "Affected Wards",
    "Evacuation & Shelters",
    "Recommended Actions",
    "Data Sources & Confidence",
)
MAX_SUMMARY_CHARS = 700

ACTIONS = {
    "red": [
        "Issue the approved public alert to the target wards immediately (SMS + WhatsApp).",
        "Open and staff the identified shelters and relief camps; arrange food, water, medical teams.",
        "Request pre-positioning of SDRF/NDRF teams and boats in the highest-risk wards.",
        "Begin assisted evacuation of the elderly, disabled, pregnant women and children.",
        "Close underpasses and low-lying roads; coordinate with police for traffic diversion.",
        "Brief hospitals on possible casualty surge; secure power backup.",
    ],
    "orange": [
        "Get the public alert approved and dispatched to the target wards.",
        "Place shelters on standby; check capacity, water, sanitation and power.",
        "Alert SDRF/NDRF and municipal quick-response teams; inspect drains and pumps.",
        "Identify vulnerable households for early assisted evacuation.",
    ],
    "yellow": [
        "Monitor IMD and CWC bulletins every 3 hours.",
        "Clear drains and check pumping stations in low-lying wards.",
        "Verify shelter readiness and update contact lists.",
    ],
    "green": [
        "Routine monitoring; no public alert required.",
        "Use the calm period for drain cleaning and shelter maintenance.",
    ],
}


def _facts(ctx: ToolContext) -> Facts:
    return ctx.get_facts()


def compose_section(heading: str, ctx: ToolContext) -> str:
    """Deterministic body text for one sitrep section."""
    f, r = _facts(ctx), ctx.risk
    decision = ctx.extra.get("decision")
    if heading == "Situation":
        text = (
            f"{f.city} ({f.state}) is at {f.level.upper()} flood risk with an overall score of "
            f"{f.score}/100. {f.explanation}"
        )
        if decision is not None:
            text += (
                " Monitor decision: public alert drafted, pending human approval."
                if decision.should_alert
                else " Monitor decision: no public alert."
            )
        if r.stale:
            text += " Some data sources are stale (last-known values used)."
        return text
    if heading == "River & Rainfall Outlook":
        lines = []
        for g in r.gauges:
            lines.append(
                f"{g.gauge.river}: now {g.current_m3s:,.0f} m3/s, forecast peak {g.peak_m3s:,.0f} m3/s on "
                f"{g.peak_date} ({g.status}; warning {g.gauge.warning_m3s:,.0f}, danger "
                f"{g.gauge.danger_m3s:,.0f}, extreme {g.gauge.extreme_m3s:,.0f} m3/s)."
            )
        if not r.gauges:
            lines.append(
                f"No meaningful GloFAS river cell for the {f.river}; the outlook is rainfall-driven."
            )
        lines.append(
            f"Rainfall: up to {f.rain_24h_mm} mm in 24 h ({f.rain_category}), {f.rain_72h_mm} mm over "
            f"72 h, peak intensity {f.max_intensity_mmph} mm/h; {f.antecedent_7d_mm} mm fell in the past "
            f"7 days. Highest risk expected around {f.peak_time_ist}."
        )
        return "\n".join(lines)
    if heading == "Affected Wards":
        wards = {w.id: w for w in r.city.wards}
        ranked = sorted(r.wards, key=lambda w: -w.risk.score)[:5]
        rows = [
            f"- {wards[w.ward_id].name}: {w.risk.level} ({w.risk.score}), population ~"
            f"{wards[w.ward_id].population:,}, vulnerability {wards[w.ward_id].vulnerability:.2f}"
            for w in ranked
        ]
        return (
            "\n".join(rows)
            + f"\nAlert target wards: {', '.join(f.ward_names)} (~{f.population_at_risk:,} people)."
        )
    if heading == "Evacuation & Shelters":
        if not ctx.plans:
            return "No evacuation plans were required for this run."
        wards = {w.id: w for w in r.city.wards}
        rows = []
        for p in ctx.plans:
            origin = min(
                wards.values(),
                key=lambda w: (w.lat - p.origin.lat) ** 2 + (w.lon - p.origin.lon) ** 2,
            )
            rows.append(
                f"- {origin.name} -> {p.facility.name}: {p.route.distance_m / 1000:.1f} km, "
                f"~{p.route.duration_s / 60:.0f} min on foot ({p.route.method}); "
                f"{p.facility.capacity - p.facility.occupancy} free places"
            )
        return "\n".join(rows)
    if heading == "Recommended Actions":
        return "\n".join(f"- {a}" for a in ACTIONS[f.level])
    if heading == "Data Sources & Confidence":
        src = (
            "; ".join(
                f"{s.name} ({'ok' if s.ok else 'STALE'}{', fetched ' + s.fetched_at if s.fetched_at else ''})"
                for s in r.sources
            )
            or "replayed scenario data"
        )
        ml = r.overall.ml_probability
        text = (
            f"Sources: {src}. GloFAS is a ~5 km global model; thresholds are percentiles (P90/P98/P99.7) "
            "of its 1995-2024 reanalysis, not CWC danger levels. Ward boundaries, populations and "
            "facilities are synthetic. The risk score is a transparent rule-based index"
        )
        text += (
            f"; the optional ML model estimates P(flood-day) = {ml:.2f}." if ml is not None else "."
        )
        text += f" Narrative by {ctx.extra.get('provider', 'rules')}. Decision support only - verify with IMD/CWC."
        return text
    raise ValueError(heading)


def _rules_summary(f: Facts, plans: int) -> str:
    river = (
        f" The {f.river} is forecast at {f.gauge_pct_of_danger}% of its danger discharge."
        if f.has_gauge
        else ""
    )
    return (
        f"{f.city} is at {f.level} flood risk (score {f.score}/100), peaking around {f.peak_time_ist}."
        f"{river} Up to {f.rain_24h_mm} mm of rain is expected in 24 hours. "
        f"Priority wards: {', '.join(f.ward_names)} (about {f.population_at_risk:,} people); "
        f"{plans} evacuation route(s) to shelters have been planned."
    )


async def write_sitrep(
    provider: LLMProvider, ctx: ToolContext, rec: StepRecorder, run_id: str
) -> SitRep:
    f = _facts(ctx)
    sections: list[SitRepSection] = []
    for h in SECTION_HEADINGS:
        rec.add(
            AGENT,
            "tool_call",
            f"Calling compose_sitrep_section '{h}'",
            tool="compose_sitrep_section",
            input={"heading": h},
        )
        t0 = time.perf_counter()
        out = await call_tool("compose_sitrep_section", {"heading": h}, ctx)
        rec.add(
            AGENT,
            "tool_result",
            f"Section '{h}' composed",
            tool="compose_sitrep_section",
            output=out,
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        sections.append(SitRepSection(heading=h, body=out["body"]))
    summary = _rules_summary(f, len(ctx.plans))
    allowed = f.allowed_numbers() | {str(len(ctx.plans))}
    if not isinstance(provider, RulesProvider):
        messages: list[Message] = [
            {
                "role": "system",
                "content": (
                    "You write the summary paragraph of a flood situation report for an Indian district "
                    "collector. 3 sentences, at most 90 words, plain text, no headings, no lists, no links. "
                    "Use ONLY the facts given; do not invent numbers, names or times."
                ),
            },
            {
                "role": "user",
                "content": f"Facts: {f.as_dict()}\nEvacuation routes planned: {len(ctx.plans)}\n"
                f"Reference summary: {summary}\nWrite the summary.",
            },
        ]
        t0 = time.perf_counter()
        try:
            resp = await provider.chat(messages, None)
            text = re.sub(r"\s+", " ", resp.content).strip()
            bad = unverified_numbers(text, allowed)
            ok = (
                bool(text)
                and not bad
                and not URL_RE.search(text)
                and len(text) <= MAX_SUMMARY_CHARS
            )
            rec.add(
                AGENT,
                "guard",
                "LLM summary passed fact checks"
                if ok
                else f"LLM summary rejected ({'unverified numbers ' + str(bad) if bad else 'format'}); using deterministic summary",
                input={"summary": text},
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            if ok:
                summary = text
        except LLMError as exc:
            rec.add(AGENT, "error", f"Summary LLM call failed: {exc}")
    plans_free = sum(p.facility.capacity - p.facility.occupancy for p in ctx.plans)
    g = dominant_gauge(ctx.risk)
    figures = [
        KeyFigure(label="Risk level", value=f.level.upper()),
        KeyFigure(label="Risk score", value=f"{f.score}/100"),
        KeyFigure(label="Expected peak", value=f.peak_time_ist),
        KeyFigure(label="Max 24 h rain", value=f"{f.rain_24h_mm} mm ({f.rain_category})"),
        KeyFigure(
            label="River vs danger",
            value=f"{f.river} {f.gauge_pct_of_danger}% ({g.status})" if g else "no river gauge",
        ),
        KeyFigure(label="Population in target wards", value=f"{f.population_at_risk:,}"),
        KeyFigure(label="Shelter places on planned routes", value=f"{plans_free:,}"),
    ]
    rec.add(AGENT, "final", "Situation report compiled", output={"summary": summary})
    return SitRep(
        run_id=run_id,
        city_id=f.city_id,
        generated_at=fmt_ts(datetime.now(UTC)),
        title=f"Flood Situation Report - {f.city}, {f.state}",
        summary=summary,
        sections=sections,
        key_figures=figures,
    )
