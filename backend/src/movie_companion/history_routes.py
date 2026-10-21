"""Owner-derived private history; completed quiz scores come from the saved bank."""
import asyncio
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from .accounts import AccountStore, AccountError
from .account_routes import get_accounts, require_user, csrf_check
from .account_preferences import read_preferences
from .history_store import HistoryStore, VisitRequest, CompletedQuiz, ClearHistory, HistoryPage, HistoryReceipt, Kind

router=APIRouter()

def history_store(accounts:Annotated[AccountStore,Depends(get_accounts)]):return HistoryStore(accounts)

def expected_owner(request:Request,owner:Annotated[str,Depends(require_user)]):
    if request.headers.get('x-account-owner')!=owner:
        raise AccountError(401,'Your account changed. Refresh the page before saving history.')
    return owner

def history_content():
    from .main import get_content_store
    return get_content_store()

async def history_movie(request,movie_id):
    from .main import movie_detail, get_detail_provider, get_catalog_store
    return await movie_detail(movie_id,provider=get_detail_provider(request),store=get_catalog_store(request))

@router.get('/api/me/history/{kind}',response_model=HistoryPage)
def history(kind:Kind,owner:Annotated[str,Depends(require_user)],store:Annotated[HistoryStore,Depends(history_store)],
            page:Annotated[int,Query(ge=1,le=1000000)]=1,page_size:Annotated[int,Query(ge=1,le=40)]=10):
    return store.page(owner,kind,page,page_size)

@router.post('/api/me/history/movies',response_model=HistoryReceipt,dependencies=[Depends(csrf_check)])
async def record_visit(body:VisitRequest,request:Request,owner:Annotated[str,Depends(expected_owner)],
                       store:Annotated[HistoryStore,Depends(history_store)]):
    with store.accounts.connect() as db:
        enabled=read_preferences(db,owner).track_movie_history
    if not enabled:return HistoryReceipt(owner_id=owner,status='disabled',item=None)
    old=store.existing(owner,'movies',body)
    if old:return HistoryReceipt(owner_id=owner,status='recorded',item=old)
    movie=await history_movie(request,body.movie_id)
    return await asyncio.to_thread(store.record,owner,'movies',body,movie)

@router.post('/api/me/history/quizzes',response_model=HistoryReceipt,dependencies=[Depends(csrf_check)])
async def record_quiz(body:CompletedQuiz,request:Request,owner:Annotated[str,Depends(expected_owner)],
                      store:Annotated[HistoryStore,Depends(history_store)],content:Annotated[object,Depends(history_content)]):
    if not body.allow_spoilers:raise AccountError(403,'Allow spoilers to save this quiz round.')
    old=store.existing(owner,'quizzes',body)
    if old:return HistoryReceipt(owner_id=owner,status='recorded',item=old)
    saved=await asyncio.to_thread(content.load,body.movie_id)
    if saved is None:raise AccountError(404,'A saved quiz is not available for this film.')
    if saved['version']!=body.content_version or saved['prepared_at']!=body.content_prepared_at:raise AccountError(409,'The quiz changed. Reload the quiz before saving a new round.')
    questions=saved['quiz'].items
    if saved['quiz'].status!='ready' or not questions or set(body.answers)!={q.id for q in questions}:
        raise AccountError(422,'Answer every question in this saved round before adding it to history.')
    scored=[q for q in questions if q.kind!='interpretation']
    score=sum(body.answers[q.id]==q.correct_index for q in scored)
    movie=await history_movie(request,body.movie_id)
    return await asyncio.to_thread(store.record,owner,'quizzes',body,movie,score=score,scored_questions=len(scored),
                                   total_questions=len(questions),content_version=body.content_version)

@router.delete('/api/me/history/{kind}',dependencies=[Depends(csrf_check)])
def clear_history(kind:Kind,body:ClearHistory,owner:Annotated[str,Depends(expected_owner)],store:Annotated[HistoryStore,Depends(history_store)]):
    return store.clear(owner,kind)
