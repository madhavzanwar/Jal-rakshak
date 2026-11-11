"""Alert-drafter agent: drafts the public SMS + WhatsApp alert in five languages.

* English: the LLM writes the text from the verified fact sheet (via the ``draft_alert``
  tool). It must pass the guards; on failure it gets one retry with the guard feedback, then
  the vetted English template is used.
* Hindi, Marathi, Tamil, Bengali: ALWAYS rendered from vetted templates
  (``templates.py``) -- a small local model is not trusted to translate safety-critical text.
* All five versions then pass through every guard; results are attached to the alert. Any
  failed guard blocks approval (HTTP 409) until a human edits the text.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from jalrakshak.agents.facts import Facts
from jalrakshak.agents.guards import check_version, run_guards
from jalrakshak.agents.llm import (
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    RulesProvider,
    ToolCall,
    register_policy,
)
from jalrakshak.agents.react import StepRecorder, called, meta, react
from jalrakshak.agents.templates import LEVEL_WORDS, render, render_all
from jalrakshak.agents.tools import ToolContext
from jalrakshak.models import AgentName, AlertVersion, GuardResult

AGENT: AgentName = "alert_drafter"
TOOLS = ["draft_alert", "get_emergency_contacts"]

SYSTEM = """You are the Alert Drafter agent of JalRakshak. You write public flood alerts for
Indian city residents. First call draft_alert to get the verified facts and the vetted template.
Then reply with ONLY a JSON object: {{"sms": "...", "whatsapp": "..."}}
Rules (an automatic checker enforces them; violations are discarded):
- sms: at most 160 characters, plain ASCII only (no emoji, no dashes other than '-').
- Both texts must contain the words "{level_word}" and the number 112.
- Use only numbers that appear in the verified facts. Never invent numbers or times.
- Name the city and up to three wards; say clearly what people should do now.
- No links or URLs. Calm, clear, official tone. whatsapp may use a few short lines."""

JSON_RE = re.compile(r"\{.*\}", re.S)


@dataclass
class DraftResult:
    versions: list[AlertVersion]
    guards: list[GuardResult]
    english_source: str  # "llm", "llm_retry" or "template"


def _rules_policy(messages: list[Message]) -> LLMResponse:
    m = meta(messages)
    drafts = called(messages, "draft_alert")
    if not drafts:
        return LLMResponse(
            "",
            [
                ToolCall(
                    "draft_alert",
                    {
                        "level": m.get("level"),
                        "wards": m.get("wards", []),
                        "key_facts": m.get("key_facts", []),
                    },
                )
            ],
        )
    tpl = drafts[-1].get("template_en", {}) if isinstance(drafts[-1], dict) else {}
    return LLMResponse(
        json.dumps(
            {"sms": tpl.get("sms", ""), "whatsapp": tpl.get("whatsapp", "")}, ensure_ascii=False
        )
    )


register_policy(AGENT, _rules_policy)


def parse_draft(text: str) -> dict[str, str] | None:
    """Extract {"sms", "whatsapp"} from an LLM answer (tolerates code fences / prose)."""
    m = JSON_RE.search(text or "")
    if not m:
        return None
    try:
        data: Any = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    sms, wa = data.get("sms"), data.get("whatsapp")
    if not isinstance(sms, str) or not isinstance(wa, str) or not sms.strip():
        return None
    return {"sms": sms.strip(), "whatsapp": wa.strip()}


def _key_facts(f: Facts) -> list[str]:
    facts = [f"level {f.level}", f"peak around {f.peak_time_ist}"]
    if f.has_gauge:
        facts.append(
            f"{f.river} forecast at {f.gauge_pct_of_danger}% of danger level ({f.gauge_status})"
        )
    facts.append(f"max {f.rain_24h_mm} mm rain in 24 h ({f.rain_category})")
    if f.shelter:
        facts.append(f"nearest shelter: {f.shelter}")
    return facts


def _english_failures(draft: dict[str, str], f: Facts) -> dict[str, str]:
    return check_version(AlertVersion(lang="en", **draft), f.level, f.allowed_numbers())


async def draft_alert(provider: LLMProvider, ctx: ToolContext, rec: StepRecorder) -> DraftResult:
    """Run the drafter and return the guarded five-language alert."""
    f = ctx.get_facts()
    level_word = LEVEL_WORDS["en"][f.level]
    user = (
        f"Draft the public {level_word} for {f.city} (city_id '{f.city_id}'), level '{f.level}', "
        f"target wards: {', '.join(f.ward_names)}."
    )
    res = await react(
        AGENT,
        provider,
        SYSTEM.format(level_word=level_word),
        user,
        TOOLS,
        ctx,
        rec,
        max_steps=4,
        meta={"level": f.level, "wards": f.ward_names, "key_facts": _key_facts(f)},
    )
    draft = parse_draft(res.final)
    source = "llm" if not isinstance(provider, RulesProvider) and not res.used_fallback else "rules"
    fails = _english_failures(draft, f) if draft else {"parse": "answer was not the requested JSON"}
    rec.add(
        AGENT,
        "guard",
        "English draft passed all guards" if not fails else f"English draft rejected: {fails}",
        input=draft,
        output={"failures": fails},
    )
    if fails and not isinstance(provider, RulesProvider):
        draft, fails = await _retry(provider, f, draft, fails, rec)
        source = "llm_retry"
    if fails or draft is None:
        draft = render(f, "en")
        source = "template"
        rec.add(AGENT, "guard", "Falling back to the vetted English template", output=draft)
    templ = ctx.alert_draft["versions"] if ctx.alert_draft else render_all(f)
    versions = [AlertVersion(lang="en", **draft)] + [
        AlertVersion(lang=lang, **templ[lang]) for lang in ("hi", "mr", "ta", "bn")
    ]
    guards = run_guards(versions, f.level, f.allowed_numbers())
    rec.add(
        AGENT,
        "guard",
        f"{sum(g.passed for g in guards)}/{len(guards)} alert guards passed "
        f"(English from {source}; hi/mr/ta/bn from vetted templates)",
        output=[g.model_dump() for g in guards],
    )
    rec.add(
        AGENT,
        "final",
        f"Drafted {f.level} alert for {', '.join(f.ward_names)}",
        output={"en_sms": versions[0].sms},
    )
    return DraftResult(versions=versions, guards=guards, english_source=source)


async def _retry(
    provider: LLMProvider,
    f: Facts,
    draft: dict[str, str] | None,
    fails: dict[str, str],
    rec: StepRecorder,
) -> tuple[dict[str, str] | None, dict[str, str]]:
    """One corrective attempt with the guard feedback (no tools)."""
    level_word = LEVEL_WORDS["en"][f.level]
    messages: list[Message] = [
        {"role": "system", "content": SYSTEM.format(level_word=level_word)},
        {
            "role": "user",
            "content": (
                f"Verified facts: {json.dumps(f.as_dict(), ensure_ascii=False)}\n"
                f"Your previous draft: {json.dumps(draft, ensure_ascii=False)}\n"
                f"It failed these checks: {json.dumps(fails)}\n"
                'Fix it. Reply with ONLY the JSON object {"sms": ..., "whatsapp": ...}.'
            ),
        },
    ]
    t0 = time.perf_counter()
    try:
        resp = await provider.chat(messages, None)
    except LLMError as exc:
        rec.add(AGENT, "error", f"Retry failed: {exc}")
        return None, {"llm": str(exc)}
    new = parse_draft(resp.content)
    new_fails = _english_failures(new, f) if new else {"parse": "answer was not the requested JSON"}
    rec.add(
        AGENT,
        "guard",
        "Retry passed all guards" if not new_fails else f"Retry rejected: {new_fails}",
        input=new,
        output={"failures": new_fails},
        duration_ms=(time.perf_counter() - t0) * 1000,
    )
    return new, new_fails
