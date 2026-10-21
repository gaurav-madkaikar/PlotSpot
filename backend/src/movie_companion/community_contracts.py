"""Plain-text, bounded community inputs. Client JSON never supplies an author."""
from typing import Literal
from uuid import UUID
import unicodedata
from pydantic import Field, StrictBool, field_validator
from .content_proposals import StrictRecord


def clean_text(value):
    value=value.strip()
    if not value or any(unicodedata.category(c)=='Cc' and c not in '\n\t' for c in value):
        raise ValueError('Enter readable text.')
    return value


class ThreadInput(StrictRecord):
    title:str=Field(min_length=1,max_length=140)
    body:str=Field(min_length=1,max_length=5000)
    spoilers:StrictBool=False
    request_key:UUID=Field(strict=False)
    _text=field_validator('title','body')(clean_text)

class ThreadEdit(StrictRecord):
    title:str=Field(min_length=1,max_length=140)
    body:str=Field(min_length=1,max_length=5000)
    spoilers:StrictBool=False
    revision:int=Field(ge=1,le=2147483647)
    _text=field_validator('title','body')(clean_text)

class ReplyInput(StrictRecord):
    body:str=Field(min_length=1,max_length=2000)
    spoilers:StrictBool=False
    parent_id:int|None=Field(default=None,gt=0)
    request_key:UUID=Field(strict=False)
    _text=field_validator('body')(clean_text)

class ReplyEdit(StrictRecord):
    body:str=Field(min_length=1,max_length=2000)
    spoilers:StrictBool=False
    revision:int=Field(ge=1,le=2147483647)
    _text=field_validator('body')(clean_text)

class RevisionInput(StrictRecord):
    revision:int=Field(ge=1,le=2147483647)

class ReportInput(StrictRecord):
    kind:Literal['thread','reply']
    target_id:int=Field(gt=0)
    reason:Literal['spam','harassment','spoiler','other']
    details:str=Field(default='',max_length=500)

class ModerationInput(StrictRecord):
    action:Literal['dismiss','hide','restore']
    revision:int=Field(ge=1,le=2147483647)

class PostView(StrictRecord):
    id:int
    title:str|None=None
    body:str|None
    author:str
    created_at:str
    updated_at:str
    revision:int
    spoilers:bool
    spoiler_locked:bool
    removed:bool=False
    can_edit:bool
    can_delete:bool
    parent_id:int|None=None
    depth:int=0
    replies:int=0

class PostPage(StrictRecord):
    viewer_id:str
    items:list[PostView]
    page:int
    total:int
    has_more:bool

class ThreadView(StrictRecord):
    viewer_id:str
    thread:PostView

class Capabilities(StrictRecord):
    viewer_id:str
    moderator:bool

class ReportView(StrictRecord):
    id:int
    kind:Literal['thread','reply']
    target_id:int
    movie_id:int
    reason:str
    details:str|None
    reporter:str
    created_at:str
    state:str
    content_state:str
    title:str|None
    body:str|None
    spoilers:bool
    spoiler_locked:bool
    revision:int

class ReportPage(StrictRecord):
    viewer_id:str
    items:list[ReportView]
    page:int
    total:int
    has_more:bool

class MutationResult(StrictRecord):
    viewer_id:str
    id:int
