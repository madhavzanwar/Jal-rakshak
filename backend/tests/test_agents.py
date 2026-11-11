"""Agents: ReAct robustness, monitor policy guard, drafter fallback, pipeline + store gate."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from jalrakshak.adapters import osrm
from jalrakshak.agents.alert_drafter import draft_alert, parse_draft
from jalrakshak.agents.facts import build_facts
from jalrakshak.agents.llm import (
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    OllamaProvider,
    RulesProvider,
    ToolCall,
    get_provider,
)
from jalrakshak.agents.monitor import run_monitor
from jalrakshak.agents.pipeline import run_pipeline
from jalrakshak.agents.react import StepRecorder, react, trim
from jalrakshak.agents.store import GateError, Store, language_shares
from jalrakshak.agents.tools import ToolArgError, ToolContext, call_tool, validate_args
from jalrakshak.models import CityRisk

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_osrm() -> Any:
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as m:
        m.get(url__startswith=osrm.OSRM_URL).mock(side_effect=httpx.ConnectError("offline"))
        m.route(host="127.0.0.1").pass_through()
        yield m


class Scripted(LLMProvider):
    """Fake LLM replaying scripted responses (or raising)."""

    name, model = "fake", "scripted"

    def __init__(self, script: list[LLMResponse | Exception]) -> None:
        self.script = list(script)
        self.calls = 0

    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        self.calls += 1
        item = self.script.pop(0) if self.script else LLMResponse("")
        if isinstance(item, Exception):
            raise item
        return item


def ctx_for(risk: CityRisk) -> ToolContext:
    return ToolContext(city=risk.city, risk=risk, now=datetime.now(UTC))


async def test_react_rejects_malformed_tool_calls(make_risk: Callable[..., CityRisk]) -> None:
    risk = make_risk()
    provider = Scripted(
        [
            LLMResponse("", [ToolCall("launch_rockets", {})]),
            LLMResponse("", [ToolCall("get_city_risk", {"city": "x"})]),
            LLMError("boom"),
            LLMResponse("ASSESSMENT: fine.\nDECISION: ALERT"),
        ]
    )
    rec = StepRecorder("r1")
    dec = await run_monitor(provider, ctx_for(risk), rec)
    kinds = [s.kind for s in rec.steps]
    assert "guard" in kinds and "error" in kinds
    assert any("Malformed tool call" in s.content for s in rec.steps)
    assert dec.should_alert and dec.level == "red"
    assert [s.seq for s in rec.steps] == list(range(1, len(rec.steps) + 1))


async def test_react_duplicate_and_max_steps(make_risk: Callable[..., CityRisk]) -> None:
    risk = make_risk()
    same = LLMResponse("thinking", [ToolCall("get_city_risk", {"city_id": "guwahati"})])
    provider = Scripted([same] * 10)
    rec = StepRecorder("r2")
    res = await react(
        "monitor",
        provider,
        "sys",
        "user",
        ["get_city_risk"],
        ctx_for(risk),
        rec,
        max_steps=3,
        meta={"city_id": "guwahati"},
    )
    assert any("Duplicate call" in s.content for s in rec.steps)
    assert any("Reached 3 steps" in s.content for s in rec.steps)
    assert res.used_fallback and res.final
    assert any(s.kind == "thought" for s in rec.steps)


async def test_monitor_policy_guard(make_risk: Callable[..., CityRisk]) -> None:
    green = make_risk("guwahati", 0.0, 0.1)
    assert green.overall.level == "green"
    escalate = Scripted(
        [LLMResponse("ASSESSMENT: Looks bad, alert everyone now please.\nDECISION: ALERT")]
    )
    rec = StepRecorder("r3")
    dec = await run_monitor(escalate, ctx_for(green), rec)
    assert not dec.should_alert
    assert any("overridden" in s.content for s in rec.steps)
    red = make_risk()
    rec2 = StepRecorder("r4")
    dec2 = await run_monitor(Scripted([LLMResponse("DECISION: NO_ALERT")]), ctx_for(red), rec2)
    assert dec2.should_alert
    assert any("composed from tool results" in s.content for s in rec2.steps)


async def test_monitor_yellow_escalation(make_risk: Callable[..., CityRisk]) -> None:
    risk = make_risk("mumbai", 2.2, 0.0)
    assert risk.overall.level == "yellow", risk.overall.score
    up = await run_monitor(
        Scripted(
            [LLMResponse("ASSESSMENT: Rain is building over Kurla and Sion.\nDECISION: ALERT")]
        ),
        ctx_for(risk),
        StepRecorder("y1"),
    )
    assert up.should_alert
    down = await run_monitor(RulesProvider(), ctx_for(risk), StepRecorder("y2"))
    assert not down.should_alert


async def test_drafter_bad_llm_falls_back_to_template(make_risk: Callable[..., CityRisk]) -> None:
    risk = make_risk()
    ctx = ctx_for(risk)
    ctx.facts = build_facts(risk)
    bad = (
        '{"sms": "RED ALERT Guwahati: 999 mm rain, see www.flood.in", "whatsapp": "RED ALERT 112"}'
    )
    provider = Scripted(
        [
            LLMResponse("", [ToolCall("draft_alert", {"level": "red"})]),
            LLMResponse(bad),
            LLMResponse(bad),  # retry also bad
        ]
    )
    rec = StepRecorder("d1")
    res = await draft_alert(provider, ctx, rec)
    assert res.english_source == "template"
    assert all(g.passed for g in res.guards)
    assert [v.lang for v in res.versions] == ["en", "hi", "mr", "ta", "bn"]
    assert any("rejected" in s.content for s in rec.steps)


async def test_drafter_good_llm_is_used(make_risk: Callable[..., CityRisk]) -> None:
    risk = make_risk()
    ctx = ctx_for(risk)
    ctx.facts = build_facts(risk)
    good = '```json\n{"sms": "RED ALERT Guwahati: Brahmaputra above danger level. Move to safe high ground now. Call 112", "whatsapp": "RED ALERT for Guwahati. Move to higher ground. Call 112."}\n```'
    provider = Scripted(
        [LLMResponse("", [ToolCall("draft_alert", {"level": "red"})]), LLMResponse(good)]
    )
    res = await draft_alert(provider, ctx, StepRecorder("d2"))
    assert res.english_source == "llm"
    assert res.versions[0].sms.startswith("RED ALERT Guwahati")


def test_parse_draft() -> None:
    assert parse_draft("nope") is None
    assert parse_draft("{bad json}") is None
    assert parse_draft('{"sms": 1, "whatsapp": "x"}') is None
    assert parse_draft('x {"sms": "a", "whatsapp": "b"} y') == {"sms": "a", "whatsapp": "b"}


async def test_tools_validation(make_risk: Callable[..., CityRisk]) -> None:
    ctx = ctx_for(make_risk())
    with pytest.raises(ToolArgError):
        await call_tool("nope", {}, ctx)
    with pytest.raises(ToolArgError):
        await call_tool("get_city_risk", {"city_id": "mumbai"}, ctx)
    with pytest.raises(ToolArgError):
        await call_tool("draft_alert", {"level": "green"}, ctx)
    with pytest.raises(ToolArgError):
        await call_tool("plan_route", {"origin": {"lat": 1}, "facility_id": "x"}, ctx)
    with pytest.raises(ToolArgError):
        await call_tool(
            "plan_route", {"origin": {"lat": 26.1, "lon": 91.7}, "facility_id": "mumbai-f01"}, ctx
        )
    with pytest.raises(ToolArgError):
        await call_tool("compose_sitrep_section", {"heading": "Gossip"}, ctx)
    assert validate_args({"properties": {"k": {"type": "integer"}}}, {"k": "3", "junk": 1}) == {
        "k": 3
    }
    with pytest.raises(ToolArgError):
        validate_args({"properties": {"k": {"type": "number"}}}, {"k": True})
    with pytest.raises(ToolArgError):
        validate_args({}, [])
    shelters = await call_tool("find_shelters", {"lat": 26.164, "lon": 91.77, "k": 2}, ctx)
    assert len(shelters) == 2
    route = await call_tool(
        "plan_route",
        {"origin": {"lat": 26.164, "lon": 91.77}, "facility_id": shelters[0]["facility_id"]},
        ctx,
    )
    assert route["method"] == "straight_line"
    contacts = await call_tool("get_emergency_contacts", {"city_id": "Guwahati"}, ctx)
    assert any(c["number"] == "112" for c in contacts)
    gauges = await call_tool("get_gauge_status", {"city_id": "guwahati"}, ctx)
    assert gauges["gauges"][0]["dominant"]
    mumbai = ctx_for(make_risk("mumbai"))
    assert (await call_tool("get_gauge_status", {"city_id": "mumbai"}, mumbai))["gauges"] == []


def test_trim() -> None:
    assert trim("x" * 5000).endswith("...")
    assert trim(list(range(20)))[-1] == "... 8 more"


async def test_pipeline_rules_and_approval_gate(
    make_risk: Callable[..., CityRisk], tmp_path: Any
) -> None:
    store = Store(tmp_path / "s.db")
    run, alert = await run_pipeline(make_risk(), provider=RulesProvider(), store=store)
    assert alert is not None and alert.status == "pending_approval"
    assert run.alert_id == alert.id and run.llm.provider == "rules"
    assert run.sitrep is not None and len(run.sitrep.sections) == 6
    assert len(run.evacuation) == 3
    assert all(p.route.method == "straight_line" for p in run.evacuation)
    assert {s.agent for s in run.steps} == {
        "monitor",
        "alert_drafter",
        "evacuation_planner",
        "sitrep",
    }
    assert store.get_run(run.id) == run
    assert store.list_runs("guwahati")[0].id == run.id
    assert store.timeline(5)[0].run_id == run.id

    with pytest.raises(GateError) as e:
        store.approve(alert.id, " ")
    assert e.value.status == 422
    bad = [
        v.model_copy(update={"sms": "RED ALERT: 5000 dead, visit www.x.com"})
        if v.lang == "en"
        else v
        for v in alert.versions
    ]
    edited = store.edit(alert.id, bad, "Officer Das")
    assert edited.edited and not all(g.passed for g in edited.guards)
    with pytest.raises(GateError) as e:
        store.approve(alert.id, "Officer Das")
    assert e.value.status == 409
    fixed = store.edit(alert.id, alert.versions, "Officer Das")
    assert all(g.passed for g in fixed.guards)
    sent = store.approve(alert.id, "Officer Das")
    assert sent.status == "sent" and sent.reviewed_by == "Officer Das"
    assert len(sent.dispatch_log) == 10 and all(d.simulated for d in sent.dispatch_log)
    assert sum(d.recipients_estimate for d in sent.dispatch_log) > 0
    with pytest.raises(GateError) as e:
        store.reject(alert.id, "Officer Das", "late")
    assert e.value.status == 409
    with pytest.raises(GateError) as e:
        store.approve("missing", "Officer Das")
    assert e.value.status == 404
    assert store.list_alerts("sent")[0].id == alert.id


async def test_pipeline_green_no_alert_and_reject(
    make_risk: Callable[..., CityRisk], tmp_path: Any
) -> None:
    store = Store(tmp_path / "s.db")
    run, alert = await run_pipeline(
        make_risk("guwahati", 0.0, 0.1), provider=RulesProvider(), store=store
    )
    assert alert is None and not run.decision.should_alert and run.sitrep is not None
    _, alert2 = await run_pipeline(
        make_risk("chennai", 8.0, 1.1), provider=RulesProvider(), store=store
    )
    assert alert2 is not None
    rej = store.reject(alert2.id, "Officer Iyer", "duplicate")
    assert rej.status == "rejected" and rej.reviewed_by == "Officer Iyer"


def test_language_shares() -> None:
    for cid in ("guwahati", "patna", "chennai"):
        s = language_shares(cid)
        assert sum(s.values()) == pytest.approx(1.0)
    assert max(language_shares("chennai"), key=lambda k: language_shares("chennai")[k]) == "ta"


async def test_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(await get_provider("rules"), RulesProvider)
    assert (await get_provider("openai")).name == "openai"
    assert (await get_provider("gemini")).name == "gemini"
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    assert isinstance(await get_provider("ollama"), OllamaProvider)
    assert not await OllamaProvider(host="http://127.0.0.1:9").available()
    with pytest.raises(LLMError):
        await OllamaProvider(host="http://127.0.0.1:9", timeout=1).chat(
            [{"role": "user", "content": "hi"}]
        )
    assert await RulesProvider().chat(
        [{"role": "system", "content": "", "agent": "nobody"}]
    ) == LLMResponse("")
