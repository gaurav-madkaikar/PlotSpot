"""Atomic, versioned publication; serving content never calls an LLM or source."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import sqlite3
from .movie_quiz import MovieQuiz
from .movie_facts import MovieFacts
from .source_registry import valid_source_url

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data/movie-content.db"


class ContentStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS collections (movie_id INTEGER PRIMARY KEY, version TEXT NOT NULL, prepared_at TEXT NOT NULL, source_revision TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute('CREATE TABLE IF NOT EXISTS publication_receipts (job_id TEXT PRIMARY KEY, selection_sha256 TEXT NOT NULL, receipt TEXT NOT NULL)')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def validate(quiz, facts):
        MovieQuiz.model_validate(quiz.model_dump())
        MovieFacts.model_validate(facts.model_dump())
        if quiz.status != "ready" or facts.status != "ready":
            raise ValueError("Only complete ready collections can be published")
        scored = [item for item in quiz.items if item.kind != "interpretation"]
        if len(scored) < 10 or len(facts.items) < 5:
            raise ValueError("Publication needs ten scored questions and five facts")
        for items, attr in ((quiz.items, "question"), (facts.items, "text")):
            ids = [item.id for item in items]
            texts = [" ".join(getattr(item, attr).casefold().split()) for item in items]
            if len(ids) != len(set(ids)) or len(texts) != len(set(texts)):
                raise ValueError("Content IDs and text must be unique")
            if any(not item.citations for item in items):
                raise ValueError("Every item needs evidence")
        for item in scored:
            if len(set(option.strip().casefold() for option in item.options)) != 4:
                raise ValueError("Question options must be distinct")
            if not item.explanation.strip():
                raise ValueError("Every question needs an explanation")

    @staticmethod
    def validate_manifest(quiz, facts, source_revision, manifest=None):
        citations = [c for item in [*quiz.items, *facts.items] for c in item.citations]
        if manifest is None:
            refs = {c.source_ref for c in citations}
            if len(refs) != 1:
                raise ValueError("Mixed sources require an explicit revision manifest")
            manifest = {source_revision: next(iter(refs))}
        if not isinstance(manifest, dict) or not 1 <= len(manifest) <= 32 or source_revision not in manifest:
            raise ValueError("Invalid source revision manifest")
        if any(not isinstance(revision, str) or not 1 <= len(revision) <= 100 or not valid_source_url(ref) for revision, ref in manifest.items()):
            raise ValueError("Invalid source revision manifest")
        if {c.revision for c in citations} != set(manifest) or any(manifest.get(c.revision) != c.source_ref for c in citations):
            raise ValueError("Published source revision manifest must match every citation")
        return manifest

    def publish(self, movie_id, *, version, source_revision, quiz, facts, expected_prepared_at=None, source_manifest=None):
        self.validate(quiz, facts)
        manifest = self.validate_manifest(quiz, facts, source_revision, source_manifest)
        payload = json.dumps({"quiz": quiz.model_dump(), "facts": facts.model_dump(), "source_manifest": manifest})
        with self._connect() as db:
            if expected_prepared_at is not None:
                result = db.execute("UPDATE collections SET version=?, prepared_at=?, source_revision=?, payload=? WHERE movie_id=? AND prepared_at=?", (version, datetime.now(timezone.utc).isoformat(), source_revision, payload, movie_id, expected_prepared_at))
                if result.rowcount != 1:
                    raise ValueError("Collection changed during generation; reload and try again")
                return
            db.execute("INSERT INTO collections VALUES (?, ?, ?, ?, ?) ON CONFLICT(movie_id) DO UPDATE SET version=excluded.version, prepared_at=excluded.prepared_at, source_revision=excluded.source_revision, payload=excluded.payload", (movie_id, version, datetime.now(timezone.utc).isoformat(), source_revision, payload))

    def load(self, movie_id):
        with self._connect() as db:
            row = db.execute("SELECT version, prepared_at, source_revision, payload FROM collections WHERE movie_id=?", (movie_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[3])
        quiz, facts = MovieQuiz.model_validate(payload["quiz"]), MovieFacts.model_validate(payload["facts"])
        self.validate(quiz, facts)
        manifest = self.validate_manifest(quiz, facts, row[2], payload.get("source_manifest"))
        return {"source_manifest": manifest, "version": row[0], "prepared_at": row[1], "source_revision": row[2], "quiz": quiz, "facts": facts}

    def receipt(self,job_id):
        with self._connect() as db:
            row=db.execute('SELECT receipt FROM publication_receipts WHERE job_id=?',(job_id,)).fetchone()
        return None if row is None else json.loads(row[0])

    def publish_with_receipt(self,movie_id,*,job_id,selection_sha256,report_sha256,
                             reviewer,review_kind,version,source_revision,quiz,facts,
                             expected_prepared_at,source_manifest):
        """Content and audit receipt commit together; retries never overwrite again."""
        self.validate(quiz,facts)
        manifest=self.validate_manifest(quiz,facts,source_revision,source_manifest)
        payload=json.dumps({'quiz':quiz.model_dump(),'facts':facts.model_dump(),'source_manifest':manifest})
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT selection_sha256,receipt FROM publication_receipts WHERE job_id=?',(job_id,)).fetchone()
            if previous:
                if previous[0]!=selection_sha256:raise ValueError('This job already published a different selection')
                receipt=json.loads(previous[1])
                if receipt['movie_id']!=movie_id:raise ValueError('Publication receipt movie mismatch')
                return {**receipt,'replayed':True}
            row=db.execute('SELECT prepared_at FROM collections WHERE movie_id=?',(movie_id,)).fetchone()
            if (row is None and expected_prepared_at is not None or
                    row is not None and (expected_prepared_at is None or row[0]!=expected_prepared_at)):
                raise ValueError('Collection changed before reviewed publication')
            stamp=datetime.now(timezone.utc).isoformat()
            receipt={'job_id':job_id,'movie_id':movie_id,'selection_sha256':selection_sha256,
                'report_sha256':report_sha256,'reviewer':reviewer,'review_kind':review_kind,
                'version':version,'prepared_at':stamp,'payload_sha256':hashlib.sha256(payload.encode()).hexdigest(),
                'replayed':False}
            db.execute('INSERT INTO collections VALUES (?,?,?,?,?) ON CONFLICT(movie_id) DO UPDATE SET version=excluded.version,prepared_at=excluded.prepared_at,source_revision=excluded.source_revision,payload=excluded.payload',
                       (movie_id,version,stamp,source_revision,payload))
            db.execute('INSERT INTO publication_receipts VALUES (?,?,?)',
                       (job_id,selection_sha256,json.dumps(receipt)))
        return receipt
