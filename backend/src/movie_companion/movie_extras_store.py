"""A bounded durable cache for dynamic movie extras, separate from catalog metadata."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import asyncio
import sqlite3

from .tmdb_client import ProviderError

DEFAULT_PATH=Path(__file__).resolve().parents[3]/'data/private/movie-extras.db'


class MovieExtrasStore:
    def __init__(self,path=DEFAULT_PATH):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('CREATE TABLE IF NOT EXISTS extras (key TEXT PRIMARY KEY, payload TEXT NOT NULL, checked_at TEXT NOT NULL)')

    def get(self,key):
        with sqlite3.connect(self.path,timeout=10) as db:
            return db.execute('SELECT payload, checked_at FROM extras WHERE key=?',(key,)).fetchone()

    def put(self,key,result):
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('INSERT INTO extras VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,checked_at=excluded.checked_at',
                (key,result.model_dump_json(),result.checked_at.isoformat()))
            db.execute('DELETE FROM extras WHERE key IN (SELECT key FROM extras ORDER BY checked_at DESC,key LIMIT -1 OFFSET 2000)')


async def load_extra(key,model,*,store,provider,fetch,ttl,stale_for,matches=lambda value:True,now=None):
    now=now or datetime.now(timezone.utc)
    saved=None
    try:
        row=await asyncio.to_thread(store.get,key)
        if row:
            candidate=model.model_validate_json(row[0])
            checked=datetime.fromisoformat(row[1])
            if checked.tzinfo is None or candidate.checked_at != checked or not matches(candidate):
                raise ValueError('Invalid saved identity or date')
            age=now-checked
            if timedelta(0)<=age<=stale_for:
                saved=candidate.model_copy(update={'stale':True})
            if timedelta(0)<=age<ttl:
                return candidate.model_copy(update={'stale':False})
    except (ValueError,OSError,sqlite3.Error):
        raise ProviderError(503,'Saved movie extras are unavailable') from None
    if provider is None:
        if saved:
            return saved
        raise ProviderError(503,'Movie extras are unavailable right now')
    try:
        async with asyncio.timeout(12):
            result=await fetch(provider)
        result=model.model_validate(result.model_dump())
        if not matches(result):
            raise ValueError('Mismatched extras identity')
    except (ProviderError,ValueError,TimeoutError):
        if saved:
            return saved
        raise ProviderError(503,'Movie extras could not be checked') from None
    result=result.model_copy(update={'checked_at':now,'stale':False})
    try:
        await asyncio.to_thread(store.put,key,result)
    except (OSError,sqlite3.Error):
        raise ProviderError(503,'Movie extras could not be saved') from None
    return result
