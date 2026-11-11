"""Live risk service: fetches open data through the cached adapters and runs the pure scoring.

Results are memoised in-process for ``JR_RISK_TTL_S`` seconds (default 300) so the dashboard and
agents can poll freely. If a source fails and nothing is cached, the city is still scored (with
zero rain / no river input) and flagged ``stale`` with the source marked ``ok=false``.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable
from datetime import UTC, datetime

from jalrakshak.adapters import openmeteo
from jalrakshak.adapters.cache import CacheResult
from jalrakshak.adapters.http import FetchError
from jalrakshak.adapters.osrm import haversine_m
from jalrakshak.data.cities import all_cities, get_city
from jalrakshak.evacuation import nearest_ward, plan_evacuation
from jalrakshak.models import City, CityRisk, CitySummary, PointRisk, SourceStatus
from jalrakshak.risk.advice import advice_for
from jalrakshak.risk.assess import DischargeSeries, MLFn, RainSeries, assess_city, summarise
from jalrakshak.risk.series import fmt_ts


def load_ml() -> MLFn | None:
    """Return the optional ML predictor, or None if the ml package is unavailable."""
    try:
        from jalrakshak.ml.predict import flood_probability
    except ImportError:
        return None
    except Exception:
        return None
    return flood_probability


class CityNotFound(KeyError):
    pass


class RiskService:
    """Fetch + score cities, with a short in-memory memo."""

    def __init__(self, ttl_s: float | None = None, ml: MLFn | None = None) -> None:
        self.ttl_s = float(os.environ.get("JR_RISK_TTL_S", "300")) if ttl_s is None else ttl_s
        self.ml = ml if ml is not None else load_ml()
        self._memo: dict[str, tuple[float, CityRisk]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def clear(self) -> None:
        self._memo.clear()

    async def city_risk(self, city_id: str) -> CityRisk:
        city = get_city(city_id)
        if city is None:
            raise CityNotFound(city_id)
        hit = self._memo.get(city.id)
        if hit is not None and time.time() - hit[0] < self.ttl_s:
            return hit[1]
        lock = self._locks.setdefault(city.id, asyncio.Lock())
        async with lock:
            hit = self._memo.get(city.id)
            if hit is not None and time.time() - hit[0] < self.ttl_s:
                return hit[1]
            risk = await self._compute(city)
            self._memo[city.id] = (time.time(), risk)
            return risk

    async def _compute(self, city: City) -> CityRisk:
        now = datetime.now(UTC)
        ward_pts = [(w.lat, w.lon) for w in city.wards]
        gauge_pts = [(g.lat, g.lon) for g in city.gauges]
        rain_res, dis_res = await asyncio.gather(
            _safe(openmeteo.fetch_rain(ward_pts)),
            _safe(openmeteo.fetch_discharge(gauge_pts)),
        )
        sources = [
            _source("Open-Meteo Forecast (hourly precipitation)", openmeteo.FORECAST_URL, rain_res),
        ]
        if city.gauges:
            sources.append(
                _source("Open-Meteo Flood API (GloFAS river discharge)", openmeteo.FLOOD_URL, dis_res)
            )
        if rain_res is not None:
            rain = [RainSeries(r["time"], r["mm"]) for r in rain_res.value]
        else:
            rain = [_zero_rain(now) for _ in city.wards]
        if dis_res is not None and city.gauges:
            dis = [DischargeSeries(d["date"], d["m3s"]) for d in dis_res.value]
            gauges_city = city
        else:
            dis, gauges_city = [], city.model_copy(update={"gauges": []})
        fetched = [r.fetched_at for r in (rain_res, dis_res) if r is not None and r.fetched_at]
        age = (time.time() - min(fetched)) / 60 if fetched else 0.0
        stale = any(not s.ok for s in sources)
        risk = assess_city(
            gauges_city,
            rain,
            dis,
            now,
            sources=sources,
            stale=stale,
            data_age_minutes=age,
            ml=self.ml,
        )
        return risk.model_copy(update={"city": city}) if gauges_city is not city else risk

    async def summaries(self) -> list[CitySummary]:
        cities = list(all_cities().values())
        if any(self._memo.get(c.id) is None for c in cities):
            await openmeteo.prefetch(
                [[(w.lat, w.lon) for w in c.wards] for c in cities],
                [[(g.lat, g.lon) for g in c.gauges] for c in cities],
            )
        risks = await asyncio.gather(*(self.city_risk(cid) for cid in all_cities()))
        return [summarise(r) for r in risks]

    async def point_risk(self, lat: float, lon: float) -> PointRisk:
        city = nearest_city(lat, lon)
        risk = await self.city_risk(city.id)
        ward = nearest_ward(city, lat, lon)
        wr = next(w.risk for w in risk.wards if w.ward_id == ward.id)
        plan = await plan_evacuation(city, lat, lon)
        return PointRisk(
            lat=lat,
            lon=lon,
            city=city,
            ward=ward,
            distance_to_city_km=round(haversine_m(lat, lon, city.lat, city.lon) / 1000, 2),
            risk=wr,
            advice=advice_for(wr.level),
            evacuation=plan,
            emergency=city.emergency,
            stale=risk.stale,
        )


def nearest_city(lat: float, lon: float) -> City:
    return min(all_cities().values(), key=lambda c: haversine_m(lat, lon, c.lat, c.lon))


async def _safe(coro: Awaitable[CacheResult]) -> CacheResult | None:
    try:
        return await coro
    except FetchError:
        return None


def _source(name: str, url: str, res: CacheResult | None) -> SourceStatus:
    return SourceStatus(
        name=name,
        url=url,
        ok=res is not None and res.ok,
        fetched_at=res.fetched_iso if res is not None and res.fetched_at else None,
    )


def _zero_rain(now: datetime) -> RainSeries:
    t0 = now.replace(minute=0, second=0, microsecond=0).timestamp() - 168 * 3600
    times = [fmt_ts(datetime.fromtimestamp(t0 + h * 3600, UTC)) for h in range(264)]
    return RainSeries(times, [0.0] * len(times))
