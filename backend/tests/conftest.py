"""Shared fixtures: isolated cache/DB, deterministic provider and synthetic risk snapshots."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jalrakshak.data.cities import get_city
from jalrakshak.models import CityRisk
from jalrakshak.risk.assess import DischargeSeries, RainSeries, assess_city


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("JR_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JR_LLM_PROVIDER", "rules")
    yield


def hourly_times(now: datetime, hours: int = 264) -> list[str]:
    t0 = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=168)
    return [(t0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(hours)]


def daily_dates(now: datetime) -> list[str]:
    d0 = now.date() - timedelta(days=7)
    return [(d0 + timedelta(days=d)).isoformat() for d in range(14)]


@pytest.fixture
def make_risk() -> Callable[..., CityRisk]:
    """Factory: CityRisk for a city under constant rain (mm/h) and river ratio (x danger)."""

    def make(
        city_id: str = "guwahati", rain_mmph: float = 7.0, river_ratio: float = 1.05
    ) -> CityRisk:
        city = get_city(city_id)
        assert city is not None
        now = datetime.now(UTC)
        times = hourly_times(now)
        rain = [RainSeries(times, [1.0] * 168 + [rain_mmph] * 96) for _ in city.wards]
        dis = [
            DischargeSeries(daily_dates(now), [g.danger_m3s * river_ratio] * 14)
            for g in city.gauges
        ]
        return assess_city(city, rain, dis, now)

    return make
