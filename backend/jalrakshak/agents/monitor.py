"""Monitor agent: assesses the city's situation and decides whether to draft an alert.

The LLM gathers evidence through tools and writes the reasoning. A deterministic policy guard
has the last word: it MUST alert at orange or red, MUST NOT alert at green, and at yellow the
LLM may escalate (ask for an advisory) if it ends with ``DECISION: ALERT``.
"""

from __future__ import annotations

import re
from typing import Any

from jalrakshak.agents.llm import LLMProvider, LLMResponse, Message, ToolCall, register_policy
from jalrakshak.agents.react import StepRecorder, called, meta, react
from jalrakshak.agents.tools import ToolContext
from jalrakshak.models import AgentName, Decision
from jalrakshak.risk.thresholds import level_rank

AGENT: AgentName = "monitor"
TOOLS = ["get_city_risk", "get_gauge_status", "get_ward_risks"]

SYSTEM = """You are the Monitor agent of JalRakshak, a flood early-warning system for Indian cities.
Step 1: call get_city_risk, get_gauge_status and get_ward_risks (each at most once).
Step 2: answer the district control room in this exact format:
ASSESSMENT: <2-3 sentences: risk level and score, river status, rainfall, which wards are most
at risk. Use only numbers returned by the tools.>
DECISION: ALERT  (or DECISION: NO_ALERT)
Alert when the level is orange or red. At yellow, alert only if a river is above its warning
level or rain is heavy and still increasing."""

DECISION_RE = re.compile(r"DECISION:\s*(NO_ALERT|ALERT)", re.I)


def _rules_policy(messages: list[Message]) -> LLMResponse:
    cid = str(meta(messages).get("city_id", ""))
    if not called(messages, "get_city_risk"):
        return LLMResponse("", [ToolCall("get_city_risk", {"city_id": cid})])
    risk = called(messages, "get_city_risk")[-1]
    if risk.get("has_river_gauge") and not called(messages, "get_gauge_status"):
        return LLMResponse("", [ToolCall("get_gauge_status", {"city_id": cid})])
    if not called(messages, "get_ward_risks"):
        return LLMResponse("", [ToolCall("get_ward_risks", {"city_id": cid, "top_n": 3})])
    return LLMResponse(
        "ASSESSMENT: "
        + rules_assessment(
            risk, called(messages, "get_gauge_status"), called(messages, "get_ward_risks")[-1]
        )
    )


def rules_assessment(risk: dict[str, Any], gauges: list[Any], wards: list[Any]) -> str:
    """Deterministic assessment grounded in tool results (used by the rules policy)."""
    level = str(risk.get("level", "green"))
    if not risk:
        return "Risk data unavailable.\nDECISION: NO_ALERT"
    parts = [f"{risk.get('city')} is at {level} risk (score {risk.get('score')}/100)."]
    if gauges and isinstance(gauges[-1], dict) and gauges[-1].get("gauges"):
        g = next((x for x in gauges[-1]["gauges"] if x.get("dominant")), gauges[-1]["gauges"][0])
        parts.append(
            f"The {g['river']} is forecast to peak at {g['peak_pct_of_danger']}% of its danger "
            f"discharge ({g['status']})."
        )
    if isinstance(wards, list) and wards:
        names = ", ".join(f"{w['name']} ({w['score']})" for w in wards[:3] if isinstance(w, dict))
        parts.append(f"Highest-risk wards: {names}.")
    alert = level in ("orange", "red")
    parts.append("DECISION: ALERT" if alert else "DECISION: NO_ALERT")
    return " ".join(parts[:-1]) + "\n" + parts[-1]


register_policy(AGENT, _rules_policy)


async def run_monitor(provider: LLMProvider, ctx: ToolContext, rec: StepRecorder) -> Decision:
    """Run the monitor loop and apply the deterministic alert policy guard."""
    level = ctx.risk.overall.level
    user = (
        f"City: {ctx.city.name} (city_id '{ctx.city.id}'). Assess the flood situation for the next "
        "72 hours and decide whether a public alert should be drafted."
    )
    res = await react(AGENT, provider, SYSTEM, user, TOOLS, ctx, rec, meta={"city_id": ctx.city.id})
    m = DECISION_RE.search(res.final)
    llm_alert = m is not None and m.group(1).upper() == "ALERT"
    reason = re.sub(r"\s+", " ", DECISION_RE.sub("", res.final).replace("ASSESSMENT:", "")).strip()
    if len(reason) < 30:  # model skipped the prose: ground it in the tool results instead
        reason = rules_assessment(
            (res.results.get("get_city_risk") or [{}])[-1],
            res.results.get("get_gauge_status", []),
            (res.results.get("get_ward_risks") or [[]])[-1],
        ).split("\nDECISION")[0]
        rec.add(AGENT, "guard", "Assessment text missing; composed from tool results")
    reason = reason[:600]
    rank = level_rank(level)
    if rank >= 2:
        should, rule = True, f"policy: level {level} >= orange -> must alert"
    elif rank == 0:
        should, rule = False, "policy: level green -> must not alert"
    else:
        should, rule = (
            llm_alert,
            f"policy: level yellow -> agent {'escalated' if llm_alert else 'did not escalate'}",
        )
    overridden = m is not None and llm_alert != should
    rec.add(
        AGENT,
        "guard",
        rule + (" (agent recommendation overridden)" if overridden else ""),
        input={"level": level, "agent_decision": m.group(1).upper() if m else None},
        output={"should_alert": should},
    )
    decision = Decision(should_alert=should, level=level, reason=reason)
    rec.add(
        AGENT,
        "decision",
        f"{'Draft alert' if should else 'No alert'}: {reason}",
        output=decision.model_dump(),
    )
    return decision
