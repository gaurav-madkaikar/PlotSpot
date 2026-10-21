"""Authenticated movie threads, owner mutations and moderator-only report access."""
import asyncio
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query, Request
from .accounts import AccountError, AccountStore
from .account_routes import get_accounts, require_user, csrf_check
from .community_contracts import (ThreadInput,ThreadEdit,ReplyInput,ReplyEdit,RevisionInput,
    ReportInput,ModerationInput,PostPage,ThreadView,Capabilities,ReportPage,MutationResult)
from .community_store import CommunityStore
from .catalog import get_movie
from .settings import get_settings
from .movie_details import load_movie_details

router=APIRouter(dependencies=[Depends(require_user)])
Owner=Annotated[str,Depends(require_user)]
Id=Annotated[int,Path(gt=0,le=2147483647)]
Page=Annotated[int,Query(ge=1,le=10000)]


def community_store(accounts:Annotated[AccountStore,Depends(get_accounts)]):
    store=getattr(accounts,'community_store',None)
    if store is None:
        store=CommunityStore(accounts);accounts.community_store=store
    return store
Store=Annotated[CommunityStore,Depends(community_store)]

async def valid_movie(movie_id,request):
    if get_settings().data_source=='demo':
        if get_movie(movie_id) is None:raise AccountError(404,'This film is not available.')
    else:
        await load_movie_details(movie_id,store=getattr(request.app.state,'catalog_store',None),
            provider=getattr(request.app.state,'tmdb',None) if get_settings().tmdb_read_token else None)

@router.get('/api/community/capabilities',response_model=Capabilities)
def capabilities(owner:Owner,store:Store):return {'viewer_id':owner,'moderator':store.moderator(owner)}

@router.get('/api/movies/{movie_id}/threads',response_model=PostPage)
def threads(movie_id:Id,owner:Owner,store:Store,page:Page=1,allow_spoilers:bool=False):
    return store.threads(movie_id,owner,page,allow_spoilers)

@router.post('/api/movies/{movie_id}/threads',response_model=MutationResult,status_code=201,dependencies=[Depends(csrf_check)])
async def create_thread(movie_id:Id,body:ThreadInput,request:Request,owner:Owner,store:Store):
    await asyncio.to_thread(store.limit_write,owner)
    await valid_movie(movie_id,request)
    return await asyncio.to_thread(store.create_thread,movie_id,owner,body)

@router.get('/api/community/threads/{thread_id}',response_model=ThreadView)
def thread(thread_id:Id,owner:Owner,store:Store,allow_spoilers:bool=False):return store.thread(thread_id,owner,allow_spoilers)

@router.get('/api/community/threads/{thread_id}/replies',response_model=PostPage)
def replies(thread_id:Id,owner:Owner,store:Store,page:Page=1,allow_spoilers:bool=False):return store.replies(thread_id,owner,page,allow_spoilers)

@router.post('/api/community/threads/{thread_id}/replies',response_model=MutationResult,status_code=201,dependencies=[Depends(csrf_check)])
def create_reply(thread_id:Id,body:ReplyInput,owner:Owner,store:Store):
    store.limit_write(owner);return store.create_reply(thread_id,owner,body)

@router.patch('/api/community/threads/{thread_id}',response_model=MutationResult,dependencies=[Depends(csrf_check)])
def edit_thread(thread_id:Id,body:ThreadEdit,owner:Owner,store:Store):
    store.limit_write(owner);return store.edit('thread',thread_id,owner,body)

@router.patch('/api/community/replies/{reply_id}',response_model=MutationResult,dependencies=[Depends(csrf_check)])
def edit_reply(reply_id:Id,body:ReplyEdit,owner:Owner,store:Store):
    store.limit_write(owner);return store.edit('reply',reply_id,owner,body)

@router.post('/api/community/threads/{thread_id}/delete',response_model=MutationResult,dependencies=[Depends(csrf_check)])
def delete_thread(thread_id:Id,body:RevisionInput,owner:Owner,store:Store):
    store.limit_write(owner);return store.delete('thread',thread_id,owner,body.revision)

@router.post('/api/community/replies/{reply_id}/delete',response_model=MutationResult,dependencies=[Depends(csrf_check)])
def delete_reply(reply_id:Id,body:RevisionInput,owner:Owner,store:Store):
    store.limit_write(owner);return store.delete('reply',reply_id,owner,body.revision)

@router.post('/api/community/reports',response_model=MutationResult,status_code=201,dependencies=[Depends(csrf_check)])
def report(body:ReportInput,owner:Owner,store:Store):
    store.limit_write(owner);return store.report(owner,body)

@router.get('/api/community/reports',response_model=ReportPage)
def reports(owner:Owner,store:Store,page:Page=1,allow_spoilers:bool=False,state:Literal['open','resolved']='open'):
    return store.reports(owner,page,allow_spoilers,state)

@router.post('/api/community/reports/{report_id}/review',response_model=MutationResult,dependencies=[Depends(csrf_check)])
def moderate(report_id:Id,body:ModerationInput,owner:Owner,store:Store):
    store.limit_write(owner);return store.moderate(owner,report_id,body)
