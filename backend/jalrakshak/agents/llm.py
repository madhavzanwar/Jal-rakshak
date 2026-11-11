"""Pluggable LLM providers with a common tool-calling interface.

``LLMProvider.chat(messages, tools) -> LLMResponse(content, tool_calls)``

Messages use the OpenAI-style shape::

    {"role": "system"|"user"|"assistant"|"tool", "content": str,
     "tool_calls": [ToolCall...] (assistant), "name": str, "tool_call_id": str (tool)}

and tools are JSON-schema function specs ``{"name", "description", "parameters"}``.

Providers: Ollama (local, default), OpenAI-compatible, Gemini (REST) and ``RulesProvider`` --
a deterministic policy that emits the same tool calls a good LLM would, so the system always
works offline and tests are deterministic. Select with ``JR_LLM_PROVIDER`` =
``auto`` (Ollama if reachable, else rules) | ``ollama`` | ``openai`` | ``gemini`` | ``rules``.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMError(RuntimeError):
    """Provider failed (network, HTTP error, unparseable response)."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        """One chat turn; may return tool calls."""

    async def available(self) -> bool:
        return True


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            val = json.loads(raw) if raw.strip() else {}
        except ValueError as exc:
            raise LLMError(f"tool arguments are not JSON: {raw[:80]}") from exc
        if isinstance(val, dict):
            return val
    raise LLMError(f"tool arguments must be an object, got {type(raw).__name__}")


def _content(msg: Message) -> str:
    c = msg.get("content")
    return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)


# ---------------------------------------------------------------------------- Ollama


class OllamaProvider(LLMProvider):
    """Local Ollama ``/api/chat`` with native tool calling (default ``qwen2.5:3b``)."""

    name = "ollama"

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float = 0.2,
        timeout: float = 120.0,
    ) -> None:
        self.model = model or os.environ.get("JR_LLM_MODEL", "qwen2.5:3b")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        if not self.host.startswith("http"):
            self.host = f"http://{self.host}"
        self.temperature = temperature
        self.timeout = timeout

    def _messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            item: dict[str, Any] = {"role": m["role"], "content": _content(m)}
            if m.get("tool_calls"):
                item["tool_calls"] = [
                    {"function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in m["tool_calls"]
                ]
            if m["role"] == "tool" and m.get("name"):
                item["tool_name"] = m["name"]
            out.append(item)
        return out

    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(messages),
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": 8192},
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(f"{self.host}/api/chat", json=payload)
                r.raise_for_status()
                msg = r.json()["message"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"ollama: {type(exc).__name__}: {exc}") from exc
        calls = [
            ToolCall(
                name=tc["function"]["name"], arguments=_parse_args(tc["function"].get("arguments"))
            )
            for tc in msg.get("tool_calls") or []
        ]
        return LLMResponse(content=msg.get("content") or "", tool_calls=calls)

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{self.host}/api/tags")
                r.raise_for_status()
                names = {m.get("name") for m in r.json().get("models", [])}
        except (httpx.HTTPError, ValueError):
            return False
        return self.model in names or f"{self.model}:latest" in names


# ---------------------------------------------------------------------------- OpenAI-compatible


class OpenAICompatibleProvider(LLMProvider):
    """Any ``/chat/completions`` endpoint (OpenAI, Groq, vLLM, LM Studio, ...)."""

    name = "openai"

    def __init__(
        self, model: str | None = None, base_url: str | None = None, api_key: str | None = None
    ) -> None:
        self.model = model or os.environ.get("JR_OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (
            base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def _messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            item: dict[str, Any] = {"role": m["role"], "content": _content(m)}
            if m.get("tool_calls"):
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m["tool_calls"]
                ]
            if m["role"] == "tool":
                item["tool_call_id"] = m.get("tool_call_id", "")
            out.append(item)
        return out

    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(messages),
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            async with httpx.AsyncClient(
                timeout=60.0, verify=os.environ.get("SSL_CERT_FILE") or True
            ) as c:
                r = await c.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                r.raise_for_status()
                msg = r.json()["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"openai: {type(exc).__name__}: {exc}") from exc
        calls = [
            ToolCall(
                id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                name=tc["function"]["name"],
                arguments=_parse_args(tc["function"].get("arguments")),
            )
            for tc in msg.get("tool_calls") or []
        ]
        return LLMResponse(content=msg.get("content") or "", tool_calls=calls)

    async def available(self) -> bool:
        return bool(self.api_key)


# ---------------------------------------------------------------------------- Gemini


class GeminiProvider(LLMProvider):
    """Google Gemini REST ``generateContent`` with function declarations."""

    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("JR_GEMINI_MODEL", "gemini-2.0-flash")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def _payload(self, messages: list[Message], tools: list[ToolSpec] | None) -> dict[str, Any]:
        system = "\n".join(_content(m) for m in messages if m["role"] == "system")
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue
            if role == "tool":
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": m.get("name", "tool"),
                                    "response": {"result": _content(m)},
                                }
                            }
                        ],
                    }
                )
            elif role == "assistant":
                parts: list[dict[str, Any]] = []
                if _content(m):
                    parts.append({"text": _content(m)})
                for tc in m.get("tool_calls") or []:
                    parts.append({"functionCall": {"name": tc.name, "args": tc.arguments}})
                contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            else:
                contents.append({"role": "user", "parts": [{"text": _content(m)}]})
        payload: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": 0.2}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]
        return payload

    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        try:
            async with httpx.AsyncClient(
                timeout=60.0, verify=os.environ.get("SSL_CERT_FILE") or True
            ) as c:
                r = await c.post(
                    url, params={"key": self.api_key}, json=self._payload(messages, tools)
                )
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"].get("parts", [])
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"gemini: {type(exc).__name__}: {exc}") from exc
        text = "".join(p.get("text", "") for p in parts)
        calls = [
            ToolCall(
                name=p["functionCall"]["name"],
                arguments=_parse_args(p["functionCall"].get("args", {})),
            )
            for p in parts
            if "functionCall" in p
        ]
        return LLMResponse(content=text, tool_calls=calls)

    async def available(self) -> bool:
        return bool(self.api_key)


# ---------------------------------------------------------------------------- Rules

Policy = Callable[[list[Message]], LLMResponse]
_POLICIES: dict[str, Policy] = {}


def register_policy(agent: str, policy: Policy) -> None:
    """Register the deterministic policy used by RulesProvider (and as fallback) for an agent."""
    _POLICIES[agent] = policy


def rules_policy(agent: str) -> Policy | None:
    return _POLICIES.get(agent)


class RulesProvider(LLMProvider):
    """Deterministic provider: dispatches to the agent's registered policy.

    The agent name is read from the ``agent`` key of the system message (other providers
    ignore that key). Policies inspect previous tool results in ``messages`` and return the
    next tool calls or a final answer -- exactly what a well-behaved LLM would do.
    """

    name = "rules"
    model = "deterministic"

    async def chat(
        self, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        agent = next((m.get("agent") for m in messages if m["role"] == "system"), None)
        policy = _POLICIES.get(str(agent))
        if policy is None:
            return LLMResponse(content="")
        return policy(messages)


# ---------------------------------------------------------------------------- selection

_avail_cache: dict[str, tuple[float, bool]] = {}


async def _cached_available(p: LLMProvider, ttl: float = 60.0) -> bool:
    key = f"{p.name}:{p.model}"
    hit = _avail_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    ok = await p.available()
    _avail_cache[key] = (time.time(), ok)
    return ok


async def get_provider(choice: str | None = None) -> LLMProvider:
    """Resolve the configured provider (``JR_LLM_PROVIDER``), falling back to rules."""
    choice = (choice or os.environ.get("JR_LLM_PROVIDER", "auto")).lower()
    if choice == "rules":
        return RulesProvider()
    if choice == "openai":
        return OpenAICompatibleProvider()
    if choice == "gemini":
        return GeminiProvider()
    ollama = OllamaProvider()
    if choice == "ollama":
        return ollama
    return ollama if await _cached_available(ollama) else RulesProvider()


async def provider_health(choice: str | None = None) -> tuple[str, str, bool]:
    """(provider, model, available) for /api/health."""
    p = await get_provider(choice)
    return p.name, p.model, await _cached_available(p)
