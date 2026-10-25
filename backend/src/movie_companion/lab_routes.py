"""Development-only GET endpoints for sanitized reliability evidence."""

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from .lab_contracts import LabOverview, LabRunDetail, LabRunList, RunState
from .settings import get_settings


router = APIRouter(prefix="/api/lab")


def get_lab_service(request: Request):
    if not get_settings().lab_enabled:
        raise HTTPException(404, "Not found")
    service = getattr(request.app.state, "lab", None)
    if service is None:
        raise HTTPException(404, "Not found")
    return service


@router.get("/overview", response_model=LabOverview)
async def lab_overview(service=Depends(get_lab_service)):
    return await asyncio.to_thread(service.overview)


@router.get("/runs", response_model=LabRunList)
async def lab_runs(
    workflow: Literal["preparation", "story_rag"] | None = None,
    state: RunState | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    service=Depends(get_lab_service),
):
    return await asyncio.to_thread(service.list_runs, workflow, state, limit)


@router.get("/runs/{run_id}", response_model=LabRunDetail)
async def lab_run(
    run_id: Annotated[str, Path(pattern=r"^(?:prep|story)_[a-f0-9]{32}$")],
    service=Depends(get_lab_service),
):
    try:
        result = await asyncio.to_thread(service.get_run, run_id)
    except ValueError:
        raise HTTPException(422, "Invalid run ID") from None
    if result is None:
        raise HTTPException(404, "Run not found")
    return result
