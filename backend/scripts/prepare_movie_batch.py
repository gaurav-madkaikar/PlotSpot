"""Acquire and prepare the fixed twenty-film multi-source batch.

Full source text and generation checkpoints stay under ``.cache/expanded20`` or
``backend/data/private``. The eval report contains provenance and counts only.
This operator never publishes content; publication still requires an explicit
reviewed selection and the atomic publication receipt path.
"""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

import httpx

from movie_companion.catalog_store import CatalogStore
from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.movie_details import load_movie_details
from movie_companion.movie_research import ResearchDocument, source_loaders
from movie_companion.movie_source_corpus import MovieSourceCorpus
from movie_companion.movie_web_sources import MovieIdentity
from movie_companion.preparation_jobs import PreparationJobs, atomic_json
from movie_companion.proposal_evidence import evidence_pools
from movie_companion.research_jobs import ResearchPreparationJobs
from movie_companion.research_continuation import continue_incomplete_report,frozen_resume_documents,rebase_report,rebase_running_report,refine_review_report
from movie_companion.settings import get_settings
from movie_companion.source_coverage import ADDITIONAL_MOVIES, content_coverage, publisher
from movie_companion.web_corpus_store import registered_source_match
from movie_companion.web_search import FreeMovieSearch
from movie_companion.wikipedia_source import MOVIE_ARTICLES, fetch_movie_source


ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / ".cache/expanded20"
SOURCES = BATCH / "sources"
REPORT = ROOT / "evals/movie-rag/expanded-20/batch-status.json"
ACQUISITION = ROOT / "evals/movie-rag/expanded-20/acquisition.json"
MOVIES = tuple(MOVIE_ARTICLES)
TERMINAL = {"needs_review", "incomplete", "failed", "cancelled", "interrupted", "ready", "published"}


def provenance(source):
    kind = registered_source_match(source) or "wikipedia"
    return {
        "source_id": source.source_id,
        "source_ref": source.source_ref,
        "revision": source.revision,
        "kind": kind,
        "publisher": None if kind == "script" else publisher(source.source_ref),
    }


def status_record(jobs, bank):
    movies = []
    for movie_id in MOVIES:
        record = jobs.store.latest(movie_id)
        saved = bank.load(movie_id)
        movies.append({
            "movie_id": movie_id,
            "title": MOVIE_ARTICLES[movie_id],
            "state": None if record is None else record["state"],
            "phase": None if record is None else record["phase"],
            "job_id": None if record is None else record["id"],
            "records": 0 if record is None or not record.get("report") else len(record["report"].get("records", [])),
            "retained_facts": 0 if record is None or not record.get("report") else len(record["report"].get("facts", [])),
            "retained_questions": 0 if record is None or not record.get("report") else len(record["report"].get("questions", [])),
            "content_coverage": None if saved is None else content_coverage(saved["quiz"], saved["facts"]),
            "draft_coverage": None if record is None or not record.get("report") else record["report"].get("content_coverage"),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "two-publisher-movie-content-v1",
        "movie_count": len(MOVIES),
        "movies": movies,
    }


async def clients():
    settings = get_settings()
    if settings.data_source != "tmdb" or not settings.tmdb_read_token:
        raise RuntimeError("The batch requires local TMDB configuration")
    stack = []
    async def enter(**kwargs):
        client = httpx.AsyncClient(**kwargs)
        stack.append(client)
        return client
    tmdb_http = await enter(base_url="https://api.themoviedb.org/3", timeout=12,
        headers={"Authorization": f"Bearer {settings.tmdb_read_token}"}, follow_redirects=False,
        limits=httpx.Limits(max_connections=4), trust_env=False)
    wiki = await enter(base_url="https://en.wikipedia.org", timeout=30, follow_redirects=False,
        trust_env=False, headers={"User-Agent": "PlotSpot/0.2 educational source reader"})
    ollama = await enter(base_url="http://127.0.0.1:11434", timeout=180,
        follow_redirects=False, trust_env=False)
    scripts = await enter(base_url="https://imsdb.com", timeout=40, follow_redirects=False, trust_env=False)
    return stack, tmdb_http, wiki, ollama, scripts


async def environment():
    from movie_companion.tmdb_client import TmdbClient
    stack, tmdb_http, wiki, ollama, scripts = await clients()
    catalog = CatalogStore()
    tmdb = TmdbClient(tmdb_http)
    async def identity(movie_id):
        movie = await load_movie_details(movie_id, store=catalog, provider=tmdb)
        result = MovieIdentity.from_movie(movie)
        if result.movie_id != movie_id:
            raise ValueError("TMDB movie identity mismatch")
        return result
    provider = os.getenv("PLOTSPOT_MOVIE_WEB_SEARCH", "duckduckgo")
    corpus = MovieSourceCorpus(FreeMovieSearch(provider), script_client=scripts, reference_client=wiki)
    return stack, wiki, ollama, corpus, identity


async def close_environment(stack, corpus):
    await corpus.close()
    for client in reversed(stack):
        await client.aclose()


async def acquire():
    SOURCES.mkdir(parents=True, exist_ok=True)
    stack, wiki, _, corpus, identity = await environment()
    semaphore = asyncio.Semaphore(3)
    wiki_slot = asyncio.Semaphore(1)
    results = {}
    async def one(movie_id):
        async with semaphore:
            errors = []
            movie = await identity(movie_id)
            try:
                path=SOURCES / f"{movie_id}.json"
                if path.exists():
                    from movie_companion.evidence_store import SourceDocument
                    source=SourceDocument(**json.loads(path.read_text()))
                else:
                    async with wiki_slot:
                        source = await fetch_movie_source(wiki, movie_id=movie_id)
                    atomic_json(path, asdict(source))
                wiki_sources = [source]
            except (ValueError, OSError, TimeoutError, httpx.HTTPError) as error:
                wiki_sources = []
                errors.append({"branch": "wikipedia", "error_type": type(error).__name__})
            try:
                acquired = await corpus.collect(movie, refresh=True)
                public_sources = list(acquired.sources)
                trace = acquired.trace
            except (ValueError, OSError, TimeoutError, httpx.HTTPError) as error:
                public_sources, trace = [], {"degraded": True}
                errors.append({"branch": "public_sources", "error_type": type(error).__name__})
            rows = [provenance(source) for source in [*wiki_sources, *public_sources]]
            results[movie_id] = {
                "movie_id": movie_id,
                "title": movie.title,
                "year": movie.year,
                "sources": rows,
                "publishers": sorted({row["publisher"] for row in rows if row["publisher"]}),
                "trace": trace,
                "errors": errors,
            }
            print(f"acquired {movie_id} {movie.title}: {len(rows)} sources, {len(results[movie_id]['publishers'])} publishers", flush=True)
    try:
        await asyncio.gather(*(one(movie_id) for movie_id in MOVIES))
    finally:
        await close_environment(stack, corpus)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": os.getenv("PLOTSPOT_MOVIE_WEB_SEARCH", "duckduckgo"),
        "movie_count": len(MOVIES),
        "movies": [results[movie_id] for movie_id in MOVIES],
    }
    atomic_json(ACQUISITION, report)


async def refresh_wikipedia(movie_id):
    stack,_,wiki,_,_=await clients()
    try:
        source=await fetch_movie_source(wiki,movie_id=movie_id)
        evidence_pools(source)
        atomic_json(SOURCES/f'{movie_id}.json',asdict(source))
        print(f'Refreshed {movie_id}: {source.source_label} ({len(source.text)} characters).')
    finally:
        for client in reversed(stack):await client.aclose()


async def generate(movie_ids=MOVIES):
    SOURCES.mkdir(parents=True, exist_ok=True)
    stack, wiki, ollama, corpus, identity = await environment()
    class BatchResearchJobs(ResearchPreparationJobs):
        async def _research_sources(self,movie_id):
            resume=self.active.get('report') if self.active else None
            if resume is not None:return frozen_resume_documents(resume,movie_id)
            return await super()._research_sources(movie_id)
    jobs = BatchResearchJobs(wiki, ollama, asyncio.Lock(), root=BATCH / "jobs", sources=SOURCES,
        evidence_path=ROOT / "backend/data/private/expanded20-evidence", corpus=corpus,
        identity_loader=identity, require_diverse_sources=True, deadline_seconds=1800, poll_seconds=.5)
    bank = ContentStore()
    last = None
    try:
        await jobs.open()
        for movie_id in movie_ids:
            if jobs.store.latest(movie_id) is None:
                await jobs.start(movie_id, refresh=True)
        while True:
            snapshot = status_record(jobs, bank)
            atomic_json(REPORT, snapshot)
            selected=[row for row in snapshot["movies"] if row['movie_id'] in movie_ids]
            marker = tuple((row["movie_id"], row["state"], row["records"],
                row["retained_facts"], row["retained_questions"]) for row in selected)
            if marker != last:
                active = next((row for row in selected if row["state"] in {"queued", "running"}), None)
                if active:
                    print(f"preparing {active['movie_id']} {active['title']}: {active['state']} {active['records']}/50 max tasks", flush=True)
                last = marker
            if all(row["state"] in TERMINAL for row in selected):
                break
            await asyncio.sleep(2)
    finally:
        await jobs.close()
        await close_environment(stack, corpus)


def retry(movie_id):
    from movie_companion.preparation_job_store import PreparationJobStore
    store=PreparationJobStore(BATCH / "jobs/jobs.db",validate=PreparationJobs._validate)
    record=store.latest(movie_id)
    if record is None or not isinstance(record.get('report'),dict):
        raise ValueError('No checkpoint is available to retry')
    report=record['report']
    if record['state']=='incomplete':
        report=continue_incomplete_report(report)
    elif record['state'] in ('failed','interrupted'):
        if report.get('state')!='running':
            raise ValueError('The failed job has no resumable checkpoint')
        report=rebase_running_report(report)
    else:
        raise ValueError('Only an incomplete or failed job can be retried')
    store.requeue(movie_id,report=report)
    print(f'Requeued {movie_id} from {len(report.get("records", []))} validated records.')


def refine(movie_id,decisions):
    from movie_companion.preparation_job_store import PreparationJobStore
    if decisions is None or not decisions.is_file() or decisions.stat().st_size>20_000:
        raise ValueError('A bounded review decisions file is required')
    raw=json.loads(decisions.read_text())
    if (set(raw)!={'movie_id','rejections','excluded_source_ids','reviewer'}
            or raw['movie_id']!=movie_id or raw['reviewer']!='assistant_source_review'):
        raise ValueError('Invalid review decisions file')
    store=PreparationJobStore(BATCH / 'jobs/jobs.db',validate=PreparationJobs._validate)
    record=store.latest(movie_id)
    if record is None or record['state']!='needs_review':raise ValueError('Movie is not awaiting review')
    report=refine_review_report(record['report'],rejections=raw['rejections'],
                                excluded_source_ids=raw['excluded_source_ids'])
    if report['state']=='running':store.requeue(movie_id,report=report)
    elif report['state']=='needs_review':store.replace_review(movie_id,report=report)
    else:raise ValueError('Review rejection produced an invalid state')
    print(f'Requeued {movie_id} after {len(raw["rejections"])} review rejection(s).')


def rebase_jobs():
    import sqlite3
    from movie_companion.preparation_job_store import PreparationJobStore
    store=PreparationJobStore(BATCH/'jobs/jobs.db',validate=PreparationJobs._validate)
    changed=0
    with store.connection() as db:
        rows=db.execute('SELECT * FROM jobs ORDER BY sequence').fetchall()
        for row in rows:
            record=json.loads(row['payload']);report=record.get('report')
            if not isinstance(report,dict):continue
            updated=rebase_report(report)
            if updated.get('workflow_sha256')==report.get('workflow_sha256'):continue
            record['report']=updated
            db.execute('UPDATE jobs SET payload=? WHERE movie_id=?',(store.encode(record),row['movie_id']))
            changed+=1
    print(f'Revalidated and rebased {changed} checkpoint(s).')


def restart(movie_id):
    from movie_companion.preparation_job_store import PreparationJobStore
    store=PreparationJobStore(BATCH/'jobs/jobs.db',validate=PreparationJobs._validate)
    record={'id':uuid4().hex,'movie_id':movie_id,'state':'queued','phase':'source',
            'updated_at':datetime.now(timezone.utc).isoformat(),
            'message':'Waiting for fresh movie preparation.','report':None,'refresh':True}
    with store.connection() as db:
        row=db.execute('SELECT * FROM jobs WHERE movie_id=?',(movie_id,)).fetchone()
        if row is not None:
            previous=json.loads(row['payload'])
            atomic_json(BATCH/'jobs/archive'/f'{movie_id}-{row["id"]}-before-restart.json',previous)
        sequence=db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM jobs').fetchone()[0]
        db.execute('INSERT INTO jobs (movie_id,id,state,payload,sequence) VALUES (?,?,?,?,?) '
                   'ON CONFLICT(movie_id) DO UPDATE SET id=excluded.id,state=excluded.state,payload=excluded.payload,'
                   'sequence=excluded.sequence,attempts=0,owner=NULL,expires=NULL,cancel_requested=0',
                   (movie_id,record['id'],'queued',store.encode(record),sequence))
    print(f'Started a fresh checkpoint for {movie_id}; the previous checkpoint remains in the review archive.')


def show_status():
    jobs = ResearchPreparationJobs.__new__(ResearchPreparationJobs)
    from movie_companion.preparation_job_store import PreparationJobStore
    jobs.store = PreparationJobStore(BATCH / "jobs/jobs.db", validate=PreparationJobs._validate)
    payload = status_record(jobs, ContentStore())
    atomic_json(REPORT, payload)
    print(json.dumps(payload, indent=2))


def backup():
    destination = BATCH / "backups" / f"movie-content-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not DEFAULT_PATH.exists():
        raise ValueError("The movie content database does not exist")
    if destination.exists():
        raise ValueError("Backup path already exists")
    shutil.copy2(DEFAULT_PATH, destination)
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "generate", "retry", "refine", "rebase", "restart", "refresh-wikipedia", "status", "backup"))
    parser.add_argument('--movie-id',type=int)
    parser.add_argument('--decisions',type=Path)
    args = parser.parse_args()
    if args.movie_id is not None and args.movie_id not in MOVIES:
        parser.error('--movie-id must identify one of the reviewed twenty films')
    if args.action=='retry' and args.movie_id is None:
        parser.error('retry requires --movie-id')
    if args.action=='refine' and (args.movie_id is None or args.decisions is None):
        parser.error('refine requires --movie-id and --decisions')
    if args.action in ('restart','refresh-wikipedia') and args.movie_id is None:
        parser.error(f'{args.action} requires --movie-id')
    if args.movie_id is not None and args.action not in ('generate','retry','refine','restart','refresh-wikipedia'):
        parser.error('--movie-id is not available for this action')
    if tuple(ADDITIONAL_MOVIES) != MOVIES[-len(ADDITIONAL_MOVIES):]:
        raise ValueError("The reviewed twenty-film registry order changed")
    if args.action == "acquire":
        asyncio.run(acquire())
    elif args.action == "generate":
        asyncio.run(generate((args.movie_id,) if args.movie_id is not None else MOVIES))
    elif args.action == "retry":
        retry(args.movie_id)
    elif args.action == "refine":
        refine(args.movie_id,args.decisions)
    elif args.action == "rebase":
        rebase_jobs()
    elif args.action == "restart":
        restart(args.movie_id)
    elif args.action == "refresh-wikipedia":
        asyncio.run(refresh_wikipedia(args.movie_id))
    elif args.action == "backup":
        backup()
    else:
        show_status()
