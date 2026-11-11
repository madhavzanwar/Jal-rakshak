"""FastAPI app implementing every endpoint of ``docs/CONTRACT.md``.

Run: ``uvicorn jalrakshak.api.main:app``. If ``frontend/dist`` exists it is served at ``/`` so
the whole platform can ship as one container. Set ``JR_MONITOR_INTERVAL_MIN`` (> 0) to run the
agent pipeline for every city periodically (``trigger="scheduled"``); default off.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from jalrakshak import __version__
from jalrakshak.adapters import nominatim
from jalrakshak.adapters.http import FetchError
from jalrakshak.agents.llm import get_provider, provider_health
from jalrakshak.agents.pipeline import run_pipeline
from jalrakshak.agents.store import GateError, Store
from jalrakshak.data.cities import all_cities, get_city
from jalrakshak.data.facilities import city_facilities
from jalrakshak.evacuation import plan_evacuation
from jalrakshak.models import (
    AgentRun,
    AgentRunRequest,
    AgentStep,
    Alert,
    AlertEditRequest,
    AlertStatus,
    ApproveRequest,
    CityRisk,
    CitySummary,
    EvacuationPlan,
    EvacuationRequest,
    Facility,
    GeocodeResult,
    Health,
    HealthLLM,
    PointRisk,
    RejectRequest,
)
from jalrakshak.reports.pdf import sitrep_pdf
from jalrakshak.service import CityNotFound, RiskService, nearest_city

log = logging.getLogger("jalrakshak")
FRONTEND_DIST = Path(
    os.environ.get("JR_FRONTEND_DIST") or Path(__file__).resolve().parents[3] / "frontend" / "dist"
)


class State:
    service: RiskService
    store: Store


state = State()


async def _monitor_loop(minutes: float) -> None:
    while True:
        await asyncio.sleep(minutes * 60)
        for cid in all_cities():
            try:
                risk = await state.service.city_risk(cid)
                await run_pipeline(risk, trigger="scheduled", store=state.store)
            except Exception:
                log.exception("scheduled monitor failed for %s", cid)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state.service = RiskService()
    state.store = Store()
    task = None
    interval = float(os.environ.get("JR_MONITOR_INTERVAL_MIN", "0") or 0)
    if interval > 0:
        task = asyncio.create_task(_monitor_loop(interval))
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    state.store.close()


app = FastAPI(title="JalRakshak API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _gate(exc: GateError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


async def _city_risk(city_id: str) -> CityRisk:
    try:
        return await state.service.city_risk(city_id)
    except CityNotFound as exc:
        raise HTTPException(404, f"unknown city '{city_id}'") from exc


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    name, model, ok = await provider_health()
    demo = os.environ.get("JR_DEMO", "0") in ("1", "true", "yes")
    return Health(
        version=__version__, llm=HealthLLM(provider=name, model=model, available=ok), demo=demo
    )


@app.get("/api/cities", response_model=list[CitySummary])
async def cities() -> list[CitySummary]:
    return await state.service.summaries()


@app.get("/api/cities/{city_id}/risk", response_model=CityRisk)
async def city_risk(city_id: str) -> CityRisk:
    return await _city_risk(city_id)


@app.get("/api/cities/{city_id}/facilities", response_model=list[Facility])
async def facilities(city_id: str) -> list[Facility]:
    if get_city(city_id) is None:
        raise HTTPException(404, f"unknown city '{city_id}'")
    return city_facilities(city_id.lower())


@app.get("/api/risk/point", response_model=PointRisk)
async def point_risk(
    lat: float = Query(ge=6, le=38), lon: float = Query(ge=68, le=98)
) -> PointRisk:
    return await state.service.point_risk(lat, lon)


@app.get("/api/geocode", response_model=list[GeocodeResult])
async def geocode(q: str = Query(min_length=2, max_length=120)) -> list[GeocodeResult]:
    try:
        return await nominatim.geocode(q)
    except FetchError as exc:
        raise HTTPException(503, "geocoder unavailable; try again shortly") from exc


@app.post("/api/evacuation/plan", response_model=EvacuationPlan)
async def evacuation_plan(body: EvacuationRequest) -> EvacuationPlan:
    city = get_city(body.city_id) if body.city_id else nearest_city(body.lat, body.lon)
    if city is None:
        raise HTTPException(404, f"unknown city '{body.city_id}'")
    return await plan_evacuation(city, body.lat, body.lon)


@app.post("/api/agents/run", response_model=AgentRun)
async def agents_run(
    body: AgentRunRequest,
    provider: str | None = Query(default=None, description="override JR_LLM_PROVIDER"),
) -> AgentRun:
    risk = await _city_risk(body.city_id)
    run, _ = await run_pipeline(
        risk, trigger=body.trigger, provider=await get_provider(provider), store=state.store
    )
    return run


@app.get("/api/agents/runs", response_model=list[AgentRun])
async def agents_runs(
    city_id: str | None = None, limit: int = Query(50, ge=1, le=200)
) -> list[AgentRun]:
    return state.store.list_runs(city_id, limit)


@app.get("/api/agents/runs/{run_id}", response_model=AgentRun)
async def agents_run_get(run_id: str) -> AgentRun:
    run = state.store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"run '{run_id}' not found")
    return run


@app.get("/api/timeline", response_model=list[AgentStep])
async def timeline(limit: int = Query(100, ge=1, le=1000)) -> list[AgentStep]:
    return state.store.timeline(limit)


@app.get("/api/alerts", response_model=list[Alert])
async def alerts(status: AlertStatus | None = None) -> list[Alert]:
    return state.store.list_alerts(status)


@app.put("/api/alerts/{alert_id}", response_model=Alert)
async def alert_edit(alert_id: str, body: AlertEditRequest) -> Alert:
    try:
        return state.store.edit(alert_id, body.versions, body.reviewer)
    except GateError as exc:
        raise _gate(exc) from exc


@app.post("/api/alerts/{alert_id}/approve", response_model=Alert)
async def alert_approve(alert_id: str, body: ApproveRequest) -> Alert:
    try:
        return state.store.approve(alert_id, body.reviewer)
    except GateError as exc:
        raise _gate(exc) from exc


@app.post("/api/alerts/{alert_id}/reject", response_model=Alert)
async def alert_reject(alert_id: str, body: RejectRequest) -> Alert:
    try:
        return state.store.reject(alert_id, body.reviewer, body.reason)
    except GateError as exc:
        raise _gate(exc) from exc


@app.get("/api/sitrep/{run_id}.pdf")
async def sitrep(run_id: str) -> Response:
    run = state.store.get_run(run_id)
    if run is None or run.sitrep is None:
        raise HTTPException(404, f"no sitrep for run '{run_id}'")
    pdf = await asyncio.to_thread(sitrep_pdf, run.sitrep, run)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="sitrep-{run.city_id}-{run_id}.pdf"'},
    )


@app.get("/api/{rest:path}", include_in_schema=False)
async def api_404(rest: str) -> Response:
    raise HTTPException(404, f"no such endpoint /api/{rest}")


if FRONTEND_DIST.is_dir():

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        """Serve the built frontend (single-container deploy) with SPA fallback."""
        root = FRONTEND_DIST.resolve()
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            return FileResponse(target)
        return FileResponse(root / "index.html")
