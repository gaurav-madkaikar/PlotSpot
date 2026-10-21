"""Private visit events and completed rounds; no generation or personal AI memory."""
from datetime import datetime, timezone
import hashlib
import json
from typing import Annotated, Literal
from pydantic import Field
from .content_proposals import StrictRecord
from .personal_contracts import MovieId
from .accounts import AccountError
from .account_preferences import read_preferences

EventId = Annotated[str, Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')]
Kind = Literal['movies', 'quizzes']

class VisitRequest(StrictRecord):
    event_id: EventId
    movie_id: MovieId

class CompletedQuiz(VisitRequest):
    content_version: str = Field(min_length=1, max_length=120)
    content_prepared_at: str = Field(min_length=1,max_length=50)
    allow_spoilers: bool
    answers: dict[Annotated[str, Field(min_length=1,max_length=100)], Annotated[int,Field(ge=0,le=3)]] = Field(min_length=1,max_length=40)

class ClearHistory(StrictRecord):pass

class HistoryEntry(StrictRecord):
    id: EventId
    movie_id: MovieId
    title: str
    cover_url: str | None
    occurred_at: str
    score: int | None = None
    scored_questions: int | None = None
    total_questions: int | None = None
    content_version: str | None = None

class HistoryPage(StrictRecord):
    owner_id: str
    items: list[HistoryEntry]
    total: int
    page: int
    page_size: int
    total_pages: int

class HistoryReceipt(StrictRecord):
    owner_id: str
    status: Literal['recorded','disabled']
    item: HistoryEntry | None


def fingerprint(body):
    return hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True,separators=(',',':')).encode()).hexdigest()

class HistoryStore:
    def __init__(self, accounts):
        self.accounts=accounts
        with accounts.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS account_history (
                owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('movies','quizzes')),
                event_id TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(owner,kind,event_id))''')
            db.execute('CREATE INDEX IF NOT EXISTS account_history_owner_kind ON account_history(owner,kind)')

    def _existing(self,db,owner,kind,body):
        row=db.execute('SELECT fingerprint,payload FROM account_history WHERE owner=? AND kind=? AND event_id=?', (owner,kind,body.event_id)).fetchone()
        if row is None:return None
        if row['fingerprint']!=fingerprint(body):raise AccountError(409,'This history event was already saved with different details.')
        return HistoryEntry.model_validate_json(row['payload'])

    def existing(self,owner,kind,body):
        with self.accounts.connect() as db:return self._existing(db,owner,kind,body)

    def record(self,owner,kind,body,movie,**score):
        with self.accounts.connect() as db:
            if kind=='movies' and not read_preferences(db,owner).track_movie_history:
                return HistoryReceipt(owner_id=owner,status='disabled',item=None)
            old=self._existing(db,owner,kind,body)
            if old is not None:return HistoryReceipt(owner_id=owner,status='recorded',item=old)
            entry=HistoryEntry(id=body.event_id,movie_id=movie.id,title=movie.title,cover_url=movie.cover_url,
                               occurred_at=datetime.fromtimestamp(self.accounts.clock(),timezone.utc).isoformat(),**score)
            db.execute('INSERT INTO account_history VALUES (?,?,?,?,?)',(owner,kind,body.event_id,fingerprint(body),entry.model_dump_json()))
            return HistoryReceipt(owner_id=owner,status='recorded',item=entry)

    def page(self,owner,kind,page=1,page_size=10):
        # rowid provides stable newest-first event order even within the same clock tick.
        with self.accounts.connect() as db:
            total=db.execute('SELECT COUNT(*) FROM account_history WHERE owner=? AND kind=?',(owner,kind)).fetchone()[0]
            rows=db.execute('SELECT payload FROM account_history WHERE owner=? AND kind=? ORDER BY rowid DESC LIMIT ? OFFSET ?', (owner,kind,page_size,(page-1)*page_size)).fetchall()
            return HistoryPage(owner_id=owner,items=[HistoryEntry.model_validate_json(r['payload']) for r in rows],total=total,
                               page=page,page_size=page_size,total_pages=(total+page_size-1)//page_size)

    def clear(self,owner,kind):
        with self.accounts.connect() as db:db.execute('DELETE FROM account_history WHERE owner=? AND kind=?',(owner,kind))
        return {'owner_id':owner,'status':'cleared'}
