"""Evacuation-planner agent: plans routes from the top-3 risk wards to suitable shelters.

This agent is a deterministic planner (an algorithm, not an LLM): for each of the three
highest-risk wards it calls ``find_shelters`` (nearest 3 facilities by haversine, filtered by
elevation and free capacity) and ``plan_route`` (OSRM, straight-line fallback), logging every
call as a step, and keeps the quickest option with up to two alternatives.
"""

from __future__ import annotations

import time

from jalrakshak.agents.react import StepRecorder
from jalrakshak.agents.tools import ToolContext, call_tool
from jalrakshak.evacuation import plan_evacuation
from jalrakshak.models import AgentName, EvacuationPlan

AGENT: AgentName = "evacuation_planner"


async def plan_for_top_wards(
    ctx: ToolContext, rec: StepRecorder, n: int = 3
) -> list[EvacuationPlan]:
    wards = {w.id: w for w in ctx.city.wards}
    top = sorted(ctx.risk.wards, key=lambda w: -w.risk.score)[:n]
    rec.add(
        AGENT,
        "thought",
        "Planning evacuation for the highest-risk wards: "
        + ", ".join(f"{wards[w.ward_id].name} ({w.risk.score})" for w in top),
    )
    plans: list[EvacuationPlan] = []
    for wr in top:
        ward = wards[wr.ward_id]
        args = {"lat": ward.lat, "lon": ward.lon, "k": 3}
        rec.add(
            AGENT,
            "tool_call",
            f"Calling find_shelters for {ward.name}",
            tool="find_shelters",
            input=args,
        )
        t0 = time.perf_counter()
        shelters = await call_tool("find_shelters", args, ctx)
        rec.add(
            AGENT,
            "tool_result",
            f"find_shelters returned {len(shelters)} candidate(s)",
            tool="find_shelters",
            output=shelters,
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        t1 = time.perf_counter()
        plan = await plan_evacuation(ctx.city, ward.lat, ward.lon)
        rargs = {"origin": {"lat": ward.lat, "lon": ward.lon}, "facility_id": plan.facility.id}
        rec.add(
            AGENT,
            "tool_call",
            f"Calling plan_route {ward.name} -> {plan.facility.name}",
            tool="plan_route",
            input=rargs,
        )
        rec.add(
            AGENT,
            "tool_result",
            f"{plan.route.method} route {plan.route.distance_m / 1000:.1f} km, "
            f"~{plan.route.duration_s / 60:.0f} min on foot",
            tool="plan_route",
            output={
                "facility_id": plan.facility.id,
                "method": plan.route.method,
                "distance_m": plan.route.distance_m,
                "duration_s": plan.route.duration_s,
                "alternatives": [a.facility.id for a in plan.alternatives],
            },
            duration_ms=(time.perf_counter() - t1) * 1000,
        )
        plans.append(plan)
    ctx.plans = plans
    methods = {p.route.method for p in plans}
    rec.add(
        AGENT,
        "final",
        f"{len(plans)} evacuation plan(s) ready (routing: {', '.join(sorted(methods))})",
    )
    return plans
