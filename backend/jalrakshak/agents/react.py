"""A small, explicit ReAct / tool-calling loop (no framework).

Each iteration asks the provider for the next action. Tool calls are validated and executed;
every thought, tool call, tool result, guard and error is recorded as an ``AgentStep`` with
timing, inputs and outputs. Robustness rules:

* provider error or malformed tool call (unknown tool, bad args) -> log an ``error``/``guard``
  step and take the deterministic rules policy's action for that step instead;
* a repeated identical tool call is not re-executed; the model is told to finish;
* after ``max_steps`` without a final answer the rules policy's final answer is used.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jalrakshak.agents.llm import (
    LLMError,
    LLMProvider,
    LLMResponse,
    Message,
    RulesProvider,
    ToolCall,
)
from jalrakshak.agents.tools import (
    TOOLS,
    ToolArgError,
    ToolContext,
    call_tool,
    specs,
    validate_args,
)
from jalrakshak.models import AgentName, AgentStep, StepKind

MAX_OUTPUT_CHARS = 2000


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def trim(value: Any, limit: int = MAX_OUTPUT_CHARS) -> Any:
    """Keep step payloads small: long lists/strings are truncated for the timeline."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "..."
    if isinstance(value, list):
        out = [trim(v, limit // 2) for v in value[:12]]
        if len(value) > 12:
            out.append(f"... {len(value) - 12} more")
        return out
    if isinstance(value, dict):
        return {k: trim(v, limit // 2) for k, v in value.items()}
    return value


class StepRecorder:
    """Collects AgentSteps for one run (shared by all agents of a pipeline)."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.steps: list[AgentStep] = []

    def add(
        self,
        agent: AgentName,
        kind: StepKind,
        content: str,
        *,
        tool: str | None = None,
        input: Any = None,
        output: Any = None,
        duration_ms: float = 0.0,
    ) -> AgentStep:
        step = AgentStep(
            id=f"{self.run_id}-s{len(self.steps) + 1:03d}",
            run_id=self.run_id,
            seq=len(self.steps) + 1,
            agent=agent,
            kind=kind,
            ts=_now(),
            content=content,
            tool=tool,
            input=trim(input),
            output=trim(output),
            duration_ms=round(duration_ms, 1),
        )
        self.steps.append(step)
        return step


@dataclass
class ReactResult:
    final: str
    results: dict[str, list[Any]] = field(default_factory=dict)
    used_fallback: bool = False
    llm_calls: int = 0


def _tool_message(call: ToolCall, result: Any) -> Message:
    return {
        "role": "tool",
        "name": call.name,
        "tool_call_id": call.id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }


def _validate_calls(calls: list[ToolCall], allowed: list[str]) -> str | None:
    for c in calls:
        if c.name not in allowed or c.name not in TOOLS:
            return f"tool '{c.name}' is not available to this agent"
        try:
            validate_args(TOOLS[c.name].parameters, c.arguments)
        except ToolArgError as exc:
            return f"{c.name}: {exc}"
    return None


async def react(
    agent: AgentName,
    provider: LLMProvider,
    system: str,
    user: str,
    tool_names: list[str],
    ctx: ToolContext,
    rec: StepRecorder,
    max_steps: int = 6,
    meta: dict[str, Any] | None = None,
) -> ReactResult:
    """Run the loop for one agent; returns the final answer text and tool results by name.

    ``meta`` is attached to the system message for the rules policy (e.g. ``city_id``); real
    providers only send role/content.
    """
    rules = RulesProvider()
    messages: list[Message] = [
        {"role": "system", "content": system, "agent": agent, "meta": meta or {}},
        {"role": "user", "content": user},
    ]
    tools = specs(tool_names)
    result = ReactResult(final="")
    seen: dict[str, Any] = {}
    for _ in range(max_steps):
        t0 = time.perf_counter()
        resp: LLMResponse
        try:
            resp = await provider.chat(messages, tools)
            result.llm_calls += 0 if isinstance(provider, RulesProvider) else 1
        except LLMError as exc:
            rec.add(
                agent,
                "error",
                f"LLM call failed, using rules policy for this step: {exc}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            resp = await rules.chat(messages, tools)
            result.used_fallback = True
        think_ms = (time.perf_counter() - t0) * 1000
        problem = _validate_calls(resp.tool_calls, tool_names)
        if problem is not None:
            rec.add(
                agent,
                "guard",
                f"Malformed tool call rejected ({problem}); rules policy takes this step.",
                input=[{"name": c.name, "arguments": c.arguments} for c in resp.tool_calls],
            )
            resp = await rules.chat(messages, tools)
            result.used_fallback = True
        if resp.content.strip() and resp.tool_calls:
            rec.add(agent, "thought", resp.content.strip(), duration_ms=think_ms)
        if not resp.tool_calls:
            result.final = resp.content.strip()
            if not result.final:
                result.final = await _rules_finish(agent, messages, ctx, rec, result)
            return result
        messages.append(
            {"role": "assistant", "content": resp.content, "tool_calls": resp.tool_calls}
        )
        for i, call in enumerate(resp.tool_calls):
            key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, default=str)}"
            rec.add(
                agent,
                "tool_call",
                f"Calling {call.name}",
                tool=call.name,
                input=call.arguments,
                duration_ms=think_ms if i == 0 else 0.0,
            )
            t1 = time.perf_counter()
            if key in seen:
                out: Any = {
                    "note": "already called; use the earlier result and give your final answer"
                }
                rec.add(agent, "guard", f"Duplicate call to {call.name} skipped", tool=call.name)
            else:
                try:
                    out = await call_tool(call.name, call.arguments, ctx)
                    seen[key] = out
                    result.results.setdefault(call.name, []).append(out)
                except ToolArgError as exc:
                    out = {"error": str(exc)}
                    rec.add(agent, "error", f"{call.name} failed: {exc}", tool=call.name)
            rec.add(
                agent,
                "tool_result",
                _summarise(call.name, out),
                tool=call.name,
                output=out,
                duration_ms=(time.perf_counter() - t1) * 1000,
            )
            messages.append(_tool_message(call, out))
    rec.add(
        agent, "guard", f"Reached {max_steps} steps without a final answer; using rules policy."
    )
    result.final = await _rules_finish(agent, messages, ctx, rec, result)
    return result


async def _rules_finish(
    agent: AgentName,
    messages: list[Message],
    ctx: ToolContext,
    rec: StepRecorder,
    result: ReactResult,
) -> str:
    """Let the deterministic policy complete the task (running any tools it still needs)."""
    result.used_fallback = True
    rules = RulesProvider()
    for _ in range(8):
        resp = await rules.chat(messages, None)
        if not resp.tool_calls:
            return resp.content.strip()
        messages.append({"role": "assistant", "content": "", "tool_calls": resp.tool_calls})
        for call in resp.tool_calls:
            rec.add(
                agent,
                "tool_call",
                f"Calling {call.name} (rules)",
                tool=call.name,
                input=call.arguments,
            )
            t0 = time.perf_counter()
            try:
                out: Any = await call_tool(call.name, call.arguments, ctx)
                result.results.setdefault(call.name, []).append(out)
            except ToolArgError as exc:
                out = {"error": str(exc)}
            rec.add(
                agent,
                "tool_result",
                _summarise(call.name, out),
                tool=call.name,
                output=out,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            messages.append(_tool_message(call, out))
    return ""


def _summarise(name: str, out: Any) -> str:
    if isinstance(out, dict) and "error" in out:
        return f"{name} error: {out['error']}"
    if isinstance(out, list):
        return f"{name} returned {len(out)} item(s)"
    if isinstance(out, dict) and "level" in out:
        return f"{name}: level {out['level']} (score {out.get('score')})"
    return f"{name} returned"


def new_run_id() -> str:
    return f"run-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


# helpers for rules policies -------------------------------------------------------------


def meta(messages: list[Message]) -> dict[str, Any]:
    """The ``meta`` dict attached to the system message."""
    for m in messages:
        if m["role"] == "system":
            return dict(m.get("meta") or {})
    return {}


def called(messages: list[Message], name: str) -> list[Any]:
    """Parsed results of earlier calls to ``name`` in the conversation."""
    out = []
    for m in messages:
        if m["role"] == "tool" and m.get("name") == name:
            try:
                out.append(json.loads(m["content"]))
            except (ValueError, TypeError):
                out.append(m["content"])
    return out
