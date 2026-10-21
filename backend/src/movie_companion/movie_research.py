"""Read-only specialist research; concurrent I/O, no model or publication tools."""
import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from time import monotonic
from typing import Awaitable, Callable, Literal
from urllib.parse import urlsplit

import httpx

from .background_articles import DEFAULT_CACHE
from .background_registry import ARTICLES
from .evidence_store import SourceDocument
from .external_sources import ArticleSnapshot
from .proposal_evidence import evidence_pools
from .source_sections import matches_purpose
from .wikipedia_source import MOVIE_ARTICLES, fetch_movie_source

POLICY = 'bounded-movie-research-v1'
Purpose = Literal['story', 'background']


@dataclass(frozen=True)
class ResearchDocument:
    source: SourceDocument
    article: ArticleSnapshot | None = None


@dataclass(frozen=True)
class ReadFailure:
    source_id: str
    error_type: str


@dataclass(frozen=True)
class ResearchLoad:
    documents: tuple[ResearchDocument, ...] = ()
    errors: tuple[ReadFailure, ...] = ()


@dataclass(frozen=True)
class ResearchBranch:
    purpose: Purpose
    status: str
    documents: tuple[ResearchDocument, ...]
    errors: tuple[ReadFailure, ...]
    seconds: float


@dataclass(frozen=True)
class MovieResearch:
    movie_id: int
    mode: str
    branches: tuple[ResearchBranch, ...]
    seconds: float
    events: tuple[dict, ...]

    def trace(self):
        return {'policy': POLICY, 'movie_id': self.movie_id, 'mode': self.mode,
                'seconds': self.seconds, 'events': list(self.events),
                'model_calls': 0, 'published': False,
                'branches': [{'purpose': b.purpose, 'status': b.status,
                    'seconds': b.seconds, 'errors': [asdict(e) for e in b.errors],
                    'sources': [{'source_id': d.source.source_id,
                        'source_ref': d.source.source_ref, 'revision': d.source.revision,
                        'sha256': hashlib.sha256(json.dumps(asdict(d.source),
                            sort_keys=True).encode()).hexdigest()} for d in b.documents]}
                    for b in self.branches]}


def validate_load(movie_id: int, purpose: Purpose, load: ResearchLoad):
    """Researcher output cannot choose a different movie, host or content purpose."""
    if not isinstance(load, ResearchLoad) or not isinstance(load.documents, tuple):
        raise ValueError('Expected typed research output')
    allowed = ({'wikipedia'} if purpose == 'story' else
               {'wikipedia',*(r.id for r in ARTICLES.values() if r.movie_id == movie_id)})
    if (not isinstance(load.errors, tuple) or len(load.errors) > 2
            or any(not isinstance(e, ReadFailure) or e.source_id not in allowed
                   or e.error_type not in {'ValueError', 'OSError', 'HTTPError', 'TimeoutError'}
                   for e in load.errors)):
        raise ValueError('Invalid bounded operational failures')
    if len(load.documents) > (1 if purpose == 'story' else 2):
        raise ValueError('Research source budget exceeded')
    ids = set()
    for document in load.documents:
        if not isinstance(document, ResearchDocument) or not isinstance(document.source, SourceDocument):
            raise ValueError('Expected validated research document')
        source = document.source
        if source.movie_id != movie_id or source.source_id in ids:
            raise ValueError('Wrong movie or repeated research source')
        ids.add(source.source_id)
        if purpose == 'story':
            if document.article is not None or not evidence_pools(source)['story']:
                raise ValueError('Story research needs registered plot evidence')
        else:
            if document.article is None:
                if not evidence_pools(source)['background']:
                    raise ValueError('Wikipedia background research needs production evidence')
                continue
            record = ARTICLES.get(source.source_id)
            article = document.article
            if (record is None or record.movie_id != movie_id
                    or source.source_ref != record.url
                    or not isinstance(article, ArticleSnapshot) or article.source != source
                    or article.publisher != record.publisher or article.authors != record.authors
                    or article.published_at != record.published_at
                    or not source.sections or any(not matches_purpose(s.category, 'background')
                                                  for s in source.sections)):
                raise ValueError('Background research needs registered production evidence')
    return load


async def research_movie(*, movie_id: int,
                         story_loader: Callable[[], Awaitable[ResearchLoad]],
                         background_loader: Callable[[], Awaitable[ResearchLoad]],
                         mode='parallel', branch_seconds=30, deadline_seconds=65) -> MovieResearch:
    if type(movie_id) is not int or movie_id not in MOVIE_ARTICLES:
        raise ValueError('Research requires a registered movie')
    if mode not in ('parallel', 'sequential'):
        raise ValueError('Unknown research execution mode')
    for value, maximum in ((branch_seconds, 60), (deadline_seconds, 120)):
        if type(value) not in (int, float) or not .01 <= value <= maximum:
            raise ValueError('Research deadline exceeds its budget')
    started, results, events = monotonic(), {}, []

    async def run(purpose, loader):
        instant = monotonic()
        events.append({'purpose': purpose, 'event': 'started', 'offset_seconds': round(instant-started, 6)})
        try:
            async with asyncio.timeout(branch_seconds):
                load = validate_load(movie_id, purpose, await loader())
            status = ('partial' if load.errors else 'complete') if load.documents else (
                'failed' if load.errors else 'unavailable')
        except (ValueError, OSError, httpx.HTTPError, TimeoutError) as error:
            status = 'timed_out' if isinstance(error, TimeoutError) else 'failed'
            # Never persist response bodies, exception messages or credentials.
            load = ResearchLoad(errors=(ReadFailure(
                'wikipedia' if purpose == 'story' else 'background',
                'HTTPError' if isinstance(error, httpx.HTTPError) else
                'OSError' if isinstance(error, OSError) else type(error).__name__),))
        results[purpose] = ResearchBranch(purpose, status, load.documents, load.errors,
                                         round(monotonic()-instant, 6))
        events.append({'purpose': purpose, 'event': status,
                       'offset_seconds': round(monotonic()-started, 6)})

    try:
        async with asyncio.timeout(deadline_seconds):
            if mode == 'parallel':
                async with asyncio.TaskGroup() as group:
                    group.create_task(run('story', story_loader))
                    group.create_task(run('background', background_loader))
            else:
                await run('story', story_loader)
                await run('background', background_loader)
    except TimeoutError:
        # TaskGroup has cancelled and joined unfinished branches before here.
        pass
    for purpose in ('story', 'background'):
        if purpose not in results:
            results[purpose] = ResearchBranch(purpose, 'timed_out', (),
                (ReadFailure('workflow', 'TimeoutError'),), 0)
            events.append({'purpose': purpose, 'event': 'workflow_deadline',
                           'offset_seconds': round(monotonic()-started, 6)})
    return MovieResearch(movie_id, mode, tuple(results[p] for p in ('story', 'background')),
                         round(monotonic()-started, 6), tuple(events))


def source_loaders(movie_id, *, sources: Path, article_cache=DEFAULT_CACHE,
                   refresh=False):
    """Cached by default. Explicit refresh uses only fixed registered HTTPS URLs.

    Expected article failures preserve other articles. Reads are serial within
    the background branch, so at most two network operations overlap overall.
    Refresh returns snapshots without rewriting any cache or saved collection.
    """
    if type(movie_id) is not int or movie_id not in MOVIE_ARTICLES or type(refresh) is not bool:
        raise ValueError('Use a registered movie and boolean refresh choice')
    async def story():
        if refresh:
            async with httpx.AsyncClient(base_url='https://en.wikipedia.org', timeout=25,
                    trust_env=False, follow_redirects=False) as client:
                source = await fetch_movie_source(client, movie_id=movie_id)
        else:
            def read():
                path = Path(sources)/f'{movie_id}.json'
                if path.stat().st_size > 1_000_000:
                    raise ValueError('Research snapshot exceeds budget')
                return SourceDocument(**json.loads(path.read_text()))
            source = await asyncio.to_thread(read)
        return ResearchLoad((ResearchDocument(source),))

    async def background():
        from .background_articles import fetch_article, load_article
        documents, errors = [], []
        records = [r for r in ARTICLES.values() if r.movie_id == movie_id]
        if len(records) > 2:
            raise ValueError('Background registry exceeds source budget')
        for record in records:
            try:
                if refresh:
                    parts = urlsplit(record.url)
                    async with httpx.AsyncClient(base_url=f'{parts.scheme}://{parts.netloc}',
                            timeout=25, trust_env=False, follow_redirects=False,
                            headers={'User-Agent': 'MovieCompanionLearning/0.1 (educational reader)'}) as client:
                        _, snapshot = await fetch_article(client, identifier=record.id)
                else:
                    snapshot = await asyncio.to_thread(load_article, record.id, cache_dir=article_cache)
                documents.append(ResearchDocument(snapshot.source, snapshot))
            except (ValueError, OSError, httpx.HTTPError) as error:
                errors.append(ReadFailure(record.id,
                    'HTTPError' if isinstance(error, httpx.HTTPError) else
                    'OSError' if isinstance(error, OSError) else 'ValueError'))
        return ResearchLoad(tuple(documents), tuple(errors))
    return story, background
