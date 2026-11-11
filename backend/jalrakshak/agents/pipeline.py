"""Agent pipeline: monitor -> (if alert) alert drafter -> evacuation planner -> sitrep.

Produces an ``AgentRun`` (with every step) and, when the monitor decides to alert, an
``Alert`` in ``pending_approval``. Nothing is ever sent without human approval.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jalrakshak.agents.alert_drafter import draft_alert
from jalrakshak.agents.evacuation_planner import plan_for_top_wards
from jalrakshak.agents.facts import build_facts, target_wards
from jalrakshak.agents.llm import LLMProvider, get_provider
from jalrakshak.agents.monitor import run_monitor
from jalrakshak.agents.react import StepRecorder, new_run_id
from jalrakshak.agents.sitrep import write_sitrep
from jalrakshak.agents.store import Store
from jalrakshak.agents.tools import ToolContext
from jalrakshak.evacuation import suitable_facilities
from jalrakshak.models import AgentRun, Alert, CityRisk, LLMInfo, Trigger
from jalrakshak.risk.series import fmt_ts


def _ts() -> str:
    return fmt_ts(datetime.now(UTC))


async def run_pipeline(
    risk: CityRisk,
    *,
    trigger: Trigger = "manual",
    provider: LLMProvider | None = None,
    store: Store | None = None,
) -> tuple[AgentRun, Alert | None]:
    """Run all agents on one CityRisk snapshot; persist to ``store`` if given."""
    provider = provider or await get_provider()
    run_id = new_run_id()
    started = _ts()
    rec = StepRecorder(run_id)
    ctx = ToolContext(city=risk.city, risk=risk, now=datetime.now(UTC))
    ctx.extra["provider"] = f"{provider.name} ({provider.model})"

    decision = await run_monitor(provider, ctx, rec)
    ctx.extra["decision"] = decision

    wards = target_wards(risk)
    shelters = suitable_facilities(risk.city, wards[0].lat, wards[0].lon, k=1)
    ctx.facts = build_facts(risk, shelters[0] if shelters else None)

    alert: Alert | None = None
    if decision.should_alert:
        draft = await draft_alert(provider, ctx, rec)
        alert = Alert(
            id=f"alert-{uuid.uuid4().hex[:10]}",
            run_id=run_id,
            city_id=risk.city.id,
            level=decision.level,
            status="pending_approval",
            created_at=_ts(),
            target_wards=[w.id for w in ctx.facts.wards],
            versions=draft.versions,
            guards=draft.guards,
        )

    plans = await plan_for_top_wards(ctx, rec)
    sitrep = await write_sitrep(provider, ctx, rec, run_id)

    run = AgentRun(
        id=run_id,
        city_id=risk.city.id,
        trigger=trigger,
        started_at=started,
        finished_at=_ts(),
        llm=LLMInfo(provider=provider.name, model=provider.model),
        decision=decision,
        steps=rec.steps,
        alert_id=alert.id if alert else None,
        evacuation=plans,
        sitrep=sitrep,
    )
    if store is not None:
        store.save_run(run)
        if alert is not None:
            store.save_alert(alert, ctx.facts.allowed_numbers())
    return run, alert
