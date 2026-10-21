"""Immutable acquired provenance and expiring shared movie source bundles."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from .evidence_store import SourceDocument

POLICY='movie-public-source-v1'
DEFAULT_PATH=Path(__file__).resolve().parents[2]/'data/private/web-corpus.db'

def configured_path():return Path(os.getenv('PLOTSPOT_WEB_CORPUS_DB',str(DEFAULT_PATH)))
def digest(source):return hashlib.sha256(json.dumps(asdict(source),sort_keys=True).encode()).hexdigest()

class WebCorpusStore:
    def __init__(self,path=None,*,clock=time.time):
        self.path=Path(path or configured_path());self.clock=clock
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS source_snapshots (
                movie_id INTEGER,source_id TEXT,revision TEXT,url TEXT,kind TEXT,
                policy TEXT,digest TEXT,payload TEXT,PRIMARY KEY(movie_id,source_id,revision))''')
            db.execute('CREATE INDEX IF NOT EXISTS source_snapshot_url ON source_snapshots(url,policy)')
            db.execute('CREATE TABLE IF NOT EXISTS source_bundles (key TEXT PRIMARY KEY,expires REAL,payload TEXT)')
            if 'captured_at' not in {row[1] for row in db.execute('PRAGMA table_info(source_snapshots)')}:
                db.execute('ALTER TABLE source_snapshots ADD COLUMN captured_at REAL')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            db.execute('BEGIN IMMEDIATE')
            with db:yield db
        finally:db.close()
    def remember(self,source,kind):
        if kind not in ('web','script','provider'):raise ValueError('Invalid acquired source kind')
        fingerprint=digest(source)
        with self.connect() as db:
            old=db.execute('SELECT digest FROM source_snapshots WHERE movie_id=? AND source_id=? AND revision=?',(source.movie_id,source.source_id,source.revision)).fetchone()
            if old and old[0]!=fingerprint:raise ValueError('Immutable source revision conflict')
            db.execute('INSERT OR IGNORE INTO source_snapshots VALUES (?,?,?,?,?,?,?,?,?)',(source.movie_id,source.source_id,source.revision,source.source_ref,kind,POLICY,fingerprint,json.dumps(asdict(source)),self.clock()))
    def match(self,source):
        with self.connect() as db:
            row=db.execute('SELECT digest,payload,kind,policy FROM source_snapshots WHERE movie_id=? AND source_id=? AND revision=?',(source.movie_id,source.source_id,source.revision)).fetchone()
        if not row or row[3]!=POLICY or row[0]!=digest(source):return None
        retained=SourceDocument(**json.loads(row[1]))
        if digest(retained)!=row[0]:raise ValueError('Source snapshot corrupted')
        return row[2]
    def load(self,movie_id,source_id,revision):
        with self.connect() as db:row=db.execute('SELECT payload FROM source_snapshots WHERE movie_id=? AND source_id=? AND revision=?',(movie_id,source_id,revision)).fetchone()
        if not row:raise ValueError('Acquired source is unavailable')
        source=SourceDocument(**json.loads(row[0]))
        if not self.match(source):raise ValueError('Source snapshot corrupted')
        return source
    def movie_sources(self,movie_id,*,kinds=('web','provider')):
        """Return validated immutable source snapshots for one movie."""
        if type(movie_id) is not int or movie_id <= 0:
            raise ValueError('Invalid movie ID')
        if (not isinstance(kinds,tuple) or not kinds or len(kinds)>3
                or any(kind not in ('web','script','provider') for kind in kinds)):
            raise ValueError('Invalid source kinds')
        placeholders=','.join('?' for _ in kinds)
        with sqlite3.connect(self.path,timeout=5) as db:
            rows=db.execute(
                f'SELECT digest,payload,kind,policy FROM source_snapshots WHERE movie_id=? AND kind IN ({placeholders}) ORDER BY kind,source_id,revision',
                (movie_id,*kinds)).fetchall()
        if len(rows)>64:raise ValueError('Movie source snapshot budget exceeded')
        result=[]
        for fingerprint,payload,kind,policy in rows:
            if policy!=POLICY or not isinstance(payload,str) or len(payload)>1_000_000:
                raise ValueError('Invalid retained source snapshot')
            source=SourceDocument(**json.loads(payload))
            if source.movie_id!=movie_id or digest(source)!=fingerprint:
                raise ValueError('Source snapshot corrupted')
            result.append((source,kind))
        return tuple(result)
    def save_bundle(self,key,record,*,ttl=86400):
        with self.connect() as db:db.execute('INSERT INTO source_bundles VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET expires=excluded.expires,payload=excluded.payload',(key,self.clock()+ttl,json.dumps(record)))
    def bundle(self,key,*,stale=False):
        with self.connect() as db:row=db.execute('SELECT expires,payload FROM source_bundles WHERE key=?',(key,)).fetchone()
        if not row or row[0]+(604800 if stale else 0)<=self.clock():return None
        return json.loads(row[1])

def registered_source_match(source):
    path=configured_path()
    return WebCorpusStore(path).match(source) if path.exists() else None

def registered_source(source):
    return WebCorpusStore().load(source.movie_id,source.source_id,source.revision)

def registered_url(url):
    path=configured_path()
    if not path.is_file():return False
    try:
        with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro',uri=True,timeout=1) as db:
            rows=db.execute('SELECT digest,payload FROM source_snapshots WHERE url=? AND policy=? LIMIT 32',(url,POLICY)).fetchall()
        return any((source:=SourceDocument(**json.loads(payload))).source_ref==url and digest(source)==sha for sha,payload in rows)
    except (sqlite3.Error,ValueError,OSError):return False
