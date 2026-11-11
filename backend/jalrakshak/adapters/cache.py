"""File-based JSON cache with TTL and stale-on-error fallback.

``get_or_fetch`` returns the fresh cached value if younger than ``ttl_s``; otherwise it calls
``fetch``. If the fetch fails, the last-known value is returned with ``stale=True`` so the
platform keeps working (and says so) when an upstream API is down.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jalrakshak.adapters.http import FetchError

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "var" / "cache"


def cache_dir() -> Path:
    return Path(os.environ.get("JR_CACHE_DIR") or DEFAULT_DIR)


@dataclass
class CacheResult:
    value: Any
    stale: bool
    ok: bool  # True if the value is fresh (from cache within TTL or a successful fetch)
    fetched_at: float  # epoch seconds when the value was fetched upstream

    @property
    def fetched_iso(self) -> str:
        return datetime.fromtimestamp(self.fetched_at, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class FileCache:
    """Tiny JSON-on-disk cache; one file per key (sha1 of the key)."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or cache_dir()

    def _path(self, key: str) -> Path:
        return self.directory / f"{hashlib.sha1(key.encode()).hexdigest()}.json"

    def read(self, key: str) -> tuple[Any, float] | None:
        path = self._path(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data["value"], float(data["fetched_at"])
        except (OSError, ValueError, KeyError):
            return None

    def write(self, key: str, value: Any, fetched_at: float | None = None) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        payload = {"key": key, "fetched_at": fetched_at or time.time(), "value": value}
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    async def get_or_fetch(
        self, key: str, ttl_s: float, fetch: Callable[[], Awaitable[Any]]
    ) -> CacheResult:
        cached = self.read(key)
        now = time.time()
        if cached is not None and now - cached[1] < ttl_s:
            return CacheResult(cached[0], stale=False, ok=True, fetched_at=cached[1])
        try:
            value = await fetch()
        except Exception as exc:
            if cached is not None:
                return CacheResult(cached[0], stale=True, ok=False, fetched_at=cached[1])
            raise FetchError(str(exc)) from exc
        self.write(key, value, now)
        return CacheResult(value, stale=False, ok=True, fetched_at=now)
