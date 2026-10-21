"""Durable internal preparation; queued drafts never publish movie content."""
import asyncio
from datetime import datetime, timezone
from dataclasses import asdict
import json
import logging
import os
import re
import sqlite3
from pathlib import Path
import tempfile
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .content_evidence_retrieval import MODEL, retrieve_draft_evidence
from .content_preparation import prepare_drafts
from .content_proposals import EvidenceOrigin, StrictRecord
from .evidence_store import EvidenceStore, SourceDocument
from .local_models import verify_local_model
from .proposal_evidence import evidence_pools
from .wikipedia_source import MOVIE_ARTICLES, fetch_movie_source
from .preparation_job_store import PreparationJobStore, LeaseLost
from .preparation_resume import ResumeMismatch

BACKEND = Path(__file__).resolve().parents[2]
ACTIVE = {'queued', 'running'}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.job-', delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class DraftItem(StrictRecord):
    id: str = Field(max_length=30)
    kind: Literal['fact', 'question']
    title: str = Field(max_length=250)
    text: str = Field(max_length=450)
    options: list[str] = Field(max_length=4)
    correct_index: int | None = Field(default=None, ge=0, le=3)
    decision: Literal['accept', 'reject', 'uncertain']
    retained: bool
    reason: str = Field(max_length=400)
    evidence_quote: str = Field(max_length=600)
    origin: EvidenceOrigin


class DraftJob(StrictRecord):
    id: str = Field(pattern=r'^[a-f0-9]{32}$')
    movie_id: int = Field(gt=0)
    state: Literal['queued', 'running', 'needs_review', 'incomplete', 'failed', 'cancelled', 'interrupted', 'ready', 'published']
    phase: Literal['source', 'retrieving', 'generating', 'reviewing', 'finished']
    updated_at: str = Field(max_length=40)
    message: str = Field(max_length=250)
    facts_retained: int = Field(ge=0, le=5)
    questions_retained: int = Field(ge=0, le=10)
    batches_completed: int = Field(ge=0, le=50)
    items: list[DraftItem] = Field(max_length=150)
    publication_approved: bool = False
    refresh: bool = False


class DraftStatus(StrictRecord):
    available: bool
    job: DraftJob | None = None


class JobError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def project_job(record):
    report = record.get('report') or {}
    if not isinstance(report,dict):raise ValueError('Invalid draft report')
    if report.get('workflow')=='reviewed-research-workflow-v1':
        from .research_jobs import project_research_job
        return project_research_job(record)
    if not isinstance(report,dict) or not isinstance(report.get('batches',[]),list) or len(report.get('batches',[]))>12:
        raise ValueError('Invalid draft report')
    items = []
    for batch in report.get('batches', []):
        reviews = {d['item_id']: d for d in batch['review']['items']}
        selections = {d['item_id']: d for d in batch['selection']}
        evidence = {e['passage_id']: e for e in batch['evidence']}
        for kind, key, prefix in [('fact', 'facts', 'F'), ('question', 'questions', 'Q')]:
            for index, proposal in enumerate(batch['proposals'][key]):
                item_id = prefix+str(index+1)
                passage = evidence.get(proposal['passage_id'])
                # Invalid unknown-alias proposals have no trusted source to show.
                if not passage or not passage.get('origin'):
                    continue
                if (passage['origin']['movie_id'] != record['movie_id'] or not re.fullmatch(
                        r'https://en\.wikipedia\.org/w/index\.php\?oldid=[1-9][0-9]*', passage['origin']['source_ref'])):
                    raise ValueError('Invalid draft source identity')
                selection = selections[item_id]
                reason = reviews[item_id]['reason']
                if not selection['retained'] and reviews[item_id]['decision'] == 'accept':
                    reason = {'overlapping_wording':'Similar to an earlier draft.',
                              'reused_evidence_quote':'This evidence was already used.',
                              'target_already_reached':'The draft target has been reached.'}.get(selection['reason'], 'Not retained.')
                items.append(DraftItem(id=f"b{batch['batch']}-{item_id}", kind=kind,
                    title=proposal['title'] if kind=='fact' else proposal['question'],
                    text=proposal['text'] if kind=='fact' else '',
                    options=proposal.get('options',[]), correct_index=proposal.get('correct_index'),
                    decision=reviews[item_id]['decision'], retained=selection['retained'], reason=reason,
                    evidence_quote=passage['text'], origin=EvidenceOrigin(**passage['origin'])))
    return DraftJob(**{k:v for k,v in record.items() if k!='report'},
                    facts_retained=len(report.get('facts',[])),
                    questions_retained=len(report.get('questions',[])),
                    batches_completed=len(report.get('batches',[])), items=items)


class PreparationJobs:
    def __init__(self, wiki, ollama, slot, *, root=None, sources=None, evidence_path=None, runner=None,
                 clock=None, lease_seconds=30, poll_seconds=0.25):
        self.wiki, self.ollama, self.slot = wiki, ollama, slot
        self.root = root or BACKEND/'data/private/preparation-jobs'
        self.sources = sources or BACKEND.parent/'.cache/source-snapshots'
        self.evidence_path = evidence_path or BACKEND/'data/content-evidence'
        self.runner = runner or self._prepare
        self.task = None
        self.active = None
        self.started = asyncio.Event()
        self.owner = uuid4().hex
        self.closing = False
        self.pump = None
        self.wakeup = asyncio.Event()
        self.poll_seconds = poll_seconds
        self.heartbeat_seconds = min(5,lease_seconds/3)
        self.last_heartbeat = 0
        options = {'clock':clock} if clock else {}
        self.store = PreparationJobStore(self.root/'jobs.db', validate=self._validate,
                                         lease_seconds=lease_seconds, **options)
        self.store.migrate(self.root)

    @staticmethod
    def _validate(record):
        if not isinstance(record,dict) or record.get('movie_id') not in MOVIE_ARTICLES:
            raise ValueError('Invalid registered job movie')
        project_job(record)

    def status(self, movie_id):
        if movie_id not in MOVIE_ARTICLES:
            return DraftStatus(available=False)
        try:
            record = self.store.latest(movie_id)
            return DraftStatus(available=True, job=project_job(record) if record else None)
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
            raise JobError(503, 'The draft checkpoint could not be read.') from None

    async def open(self):
        if self.closing:
            raise JobError(503, 'Preparation is shutting down.')
        if self.pump is None or self.pump.done():
            self.pump = asyncio.create_task(self._pump())
        self.wakeup.set()

    async def start(self, movie_id, *, refresh=False):
        if movie_id not in MOVIE_ARTICLES:
            raise JobError(404, 'Draft preparation is not available for this film yet.')
        if self.closing:
            raise JobError(503, 'Preparation is shutting down.')
        if type(refresh) is not bool:raise JobError(422,'Refresh must be boolean.')
        record = {'id':uuid4().hex, 'movie_id':movie_id, 'state':'queued', 'phase':'source',
                  'updated_at':now(), 'message':'Waiting for movie preparation.', 'report':None, 'refresh':refresh}
        try:
            self.store.enqueue(record)
            await self.open()
            await self._dispatch()
        except (OSError, ValueError, sqlite3.Error) as error:
            raise JobError(503, 'The preparation request could not be saved.') from error
        return self.status(movie_id)

    async def _dispatch(self):
        if self.active or self.closing or not self.store.leader(self.owner):
            return
        self.store.recover(self.owner)
        if self.slot.locked() or not self.store.pending():
            return
        await self.slot.acquire()
        try:
            record = self.store.claim(self.owner)
        except BaseException:
            self.slot.release()
            raise
        if record is None:
            self.slot.release()
            return
        self.active = record
        self.last_heartbeat = asyncio.get_running_loop().time()
        self.started.clear()
        self.task = asyncio.create_task(self._run(record))

    async def _pump(self):
        while not self.closing:
            try:
                if self.active:
                    owned = True
                    instant = asyncio.get_running_loop().time()
                    if instant-self.last_heartbeat>=self.heartbeat_seconds:
                        owned = self.store.heartbeat(self.owner)
                        self.last_heartbeat = instant
                    cancelled = self.store.requested_cancel(self.active['movie_id'],self.active['id'])
                    if (not owned or cancelled) and self.started.is_set():
                        self.task.cancel()
                else:
                    await self._dispatch()
            except (OSError, ValueError, LeaseLost, sqlite3.Error):
                logging.getLogger(__name__).warning('Preparation dispatcher could not access its queue')
            self.wakeup.clear()
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                pass

    def _save(self, record):
        record['updated_at'] = now()
        self.store.save(record,self.owner)

    async def _prepare(self, movie_id, checkpoint):
        async with asyncio.timeout(600):
            path = self.sources/f'{movie_id}.json'
            if path.exists():
                if path.stat().st_size > 1_000_000:
                    raise ValueError('Source file exceeds budget')
                source = SourceDocument(**json.loads(path.read_text()))
            else:
                source = await fetch_movie_source(self.wiki, movie_id=movie_id)
            if source.movie_id != movie_id:
                raise ValueError('Source identity mismatch')
            evidence_pools(source)
            if not path.exists():
                atomic_json(path, asdict(source))
            async with asyncio.timeout(30):
                await verify_local_model(self.ollama, MODEL)
                await verify_local_model(self.ollama, 'qwen3.5:9b')
            async def retrieve():
                store = await asyncio.to_thread(EvidenceStore, self.evidence_path)
                return await retrieve_draft_evidence(self.ollama, source=source, store=store)
            return await prepare_drafts(self.ollama, source=source, model='qwen3.5:9b',
                review_model='qwen3.5:9b', evidence_loader=retrieve, checkpoint=checkpoint,
                resume=self.active.get('report') if self.active else None)

    async def _run(self, record):
        self.started.set()
        def checkpoint(report):
            # Copy through JSON so later coordinator mutations cannot change a
            # persisted checkpoint or the visible state behind our back.
            record['report'] = json.loads(json.dumps(report))
            record['phase'] = report.get('phase', 'retrieving')
            record['message'] = {'retrieving':'Finding story and production evidence.',
                'generating':'Drafting facts and story questions.',
                'reviewing':'Checking the proposed content.',
                'finished':'Preparation finished. Drafts require review.'}[record['phase']]
            self._save(record)
        try:
            report = await self.runner(record['movie_id'], checkpoint)
            record['report'] = report
            record['state'] = report['state']
            record['phase'] = 'finished'
            record['message'] = ('Draft targets reached. Review the proposals below.' if report['state']=='needs_review'
                                 else 'Preparation stopped before the draft targets were reached.')
            if report['state']=='ready':record['message']='The saved collection was reused. No AI generation was needed.'
        except asyncio.CancelledError:
            if self.closing and not self.store.requested_cancel(record['movie_id'],record['id']):
                record.update(state='queued', message='Preparation paused. It will resume after restart.')
            else:
                record.update(state='cancelled', phase='finished', message='Preparation cancelled. Completed drafts are preserved.')
        except ResumeMismatch:
            record.update(state='interrupted',phase='finished',message='Saved evidence or preparation policy changed. Start a fresh preparation.')
        except LeaseLost:
            if self.store.requested_cancel(record['movie_id'],record['id']):
                record.update(state='cancelled',phase='finished',message='Preparation cancelled. Completed drafts are preserved.')
        except Exception as error:
            logging.getLogger(__name__).warning('Draft preparation failed: %s', type(error).__name__)
            record.update(state='failed', phase='finished', message='Preparation could not finish. Check the local AI service and try again.')
        finally:
            try:
                self._save(record)
            except (OSError, LeaseLost, sqlite3.Error):
                logging.getLogger(__name__).warning('Final draft checkpoint could not be saved')
            self.active = None
            self.slot.release()
            self.wakeup.set()

    async def cancel(self, movie_id, job_id):
        try:
            self.store.cancel(movie_id,job_id)
        except ValueError:
            raise JobError(409, 'This preparation is no longer active. Refresh its status.') from None
        self.wakeup.set()
        if self.active and self.active['movie_id']==movie_id and self.active['id']==job_id:
            await self.started.wait()
            if self.task and not self.task.done():
                self.task.cancel()
                await self.task
        return self.status(movie_id)

    async def close(self):
        self.closing = True
        if self.task and not self.task.done():
            await self.started.wait()
            self.task.cancel()
            await self.task
        if self.pump and not self.pump.done():
            self.pump.cancel()
            try:await self.pump
            except asyncio.CancelledError:pass
        self.store.release(self.owner)
