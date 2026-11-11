"""Shared async HTTP helpers (proxy-aware httpx client with small retry loop)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

USER_AGENT = "JalRakshak/0.1 (hackathon prototype)"
RETRY_STATUS = {429, 500, 502, 503, 504}
CONNECT_TIMEOUT_S = float(os.environ.get("JR_CONNECT_TIMEOUT_S", "5"))
MAX_CONCURRENCY = int(os.environ.get("JR_HTTP_CONCURRENCY", "4"))

_sems: dict[int, asyncio.Semaphore] = {}


def _sem() -> asyncio.Semaphore:
    """Per-event-loop limit on concurrent upstream requests (the free APIs and the sandbox
    proxy both dislike bursts)."""
    return _sems.setdefault(id(asyncio.get_running_loop()), asyncio.Semaphore(MAX_CONCURRENCY))


class FetchError(RuntimeError):
    """Raised when an upstream source cannot be fetched and no cached value exists."""


def make_client(timeout: float = 20.0) -> httpx.AsyncClient:
    """httpx client honouring HTTPS_PROXY and the sandbox CA bundle (SSL_CERT_FILE)."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=min(timeout, CONNECT_TIMEOUT_S)),
        verify=os.environ.get("SSL_CERT_FILE") or True,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


async def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 20.0,
    retries: int = 3,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """GET ``url`` and decode JSON, retrying transient failures with a short backoff."""
    last: Exception | None = None
    own = client is None
    c = client or make_client(timeout)
    try:
        for attempt in range(retries + 1):
            try:
                async with _sem():
                    resp = await c.get(
                        url,
                        params=params,
                        timeout=httpx.Timeout(timeout, connect=min(timeout, CONNECT_TIMEOUT_S)),
                    )
                if resp.status_code in RETRY_STATUS and attempt < retries:
                    last = FetchError(f"HTTP {resp.status_code}")
                else:
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                last = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    if exc.response.status_code != 429:
                        break
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))
    finally:
        if own:
            await c.aclose()
    raise FetchError(f"{url}: {type(last).__name__}: {last}")
