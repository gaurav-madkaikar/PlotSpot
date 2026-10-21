"""Explicit local draft operations; reads never invoke preparation."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import Field, StrictBool

from .account_routes import require_user, csrf_check
from .content_proposals import StrictRecord
from .preparation_jobs import DraftStatus, JobError

router = APIRouter(dependencies=[Depends(require_user)])


class PreparationRequest(StrictRecord):
    allow_spoilers: StrictBool = False
    refresh: StrictBool = False


class CancelPreparationRequest(PreparationRequest):
    job_id: str = Field(pattern=r'^[a-f0-9]{32}$')


def get_jobs(request: Request):
    jobs = getattr(request.app.state, 'preparation', None)
    if jobs is None:
        raise HTTPException(503, 'Draft preparation is not ready yet.')
    return jobs


def consent(allowed):
    if not allowed:
        raise HTTPException(403, 'Allow spoilers before opening movie drafts.')


@router.get('/api/movies/{movie_id}/preparation', response_model=DraftStatus)
async def preparation_status(movie_id: Annotated[int, Path(gt=0)], jobs=Depends(get_jobs), allow_spoilers: bool=False):
    consent(allow_spoilers)
    try:
        return jobs.status(movie_id)
    except JobError as error:
        raise HTTPException(error.status, error.message) from None


@router.post('/api/movies/{movie_id}/preparation', response_model=DraftStatus, status_code=202, dependencies=[Depends(csrf_check)])
async def start_preparation(movie_id: Annotated[int, Path(gt=0)], body: PreparationRequest, jobs=Depends(get_jobs)):
    consent(body.allow_spoilers)
    try:
        return await jobs.start(movie_id,refresh=True) if body.refresh else await jobs.start(movie_id)
    except JobError as error:
        raise HTTPException(error.status, error.message) from None


@router.post('/api/movies/{movie_id}/preparation/cancel', response_model=DraftStatus, dependencies=[Depends(csrf_check)])
async def cancel_preparation(movie_id: Annotated[int, Path(gt=0)], body: CancelPreparationRequest, jobs=Depends(get_jobs)):
    consent(body.allow_spoilers)
    try:
        return await jobs.cancel(movie_id, body.job_id)
    except JobError as error:
        raise HTTPException(error.status, error.message) from None
