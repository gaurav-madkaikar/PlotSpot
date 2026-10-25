"""Bounded provider discovery, separate from local semantic retrieval and AI."""
import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .catalog_store import CatalogStore
from .name_discovery import PersonNameCandidate, acting_movie_ids, director_movie_ids
from .schemas import Movie
from .tmdb_client import ProviderError, TmdbClient


class NameSearchRequest(BaseModel):
    include_adult: bool = True
    query: str = Field(min_length=1, max_length=120)
    page: int = Field(default=1, ge=1, le=100)
    person_id: int | None = Field(default=None, gt=0)
    role: Literal['actor', 'director'] = 'actor'
    genre: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    max_runtime: int | None = Field(default=None, ge=1, le=600)


class NameSearchResult(BaseModel):
    items: list[Movie]
    people: list[PersonNameCandidate] = Field(default_factory=list)
    selected_person: PersonNameCandidate | None = None
    role: Literal['actor', 'director']
    page: int
    has_more: bool
    partial: bool = False
    limited: bool = False


def matches_filters(movie, request):
    return ((request.include_adult or movie.adult is not True)
            and (not request.genre or request.genre.strip().casefold() in {g.casefold() for g in movie.genres})
            and (not request.language or request.language.strip().casefold() == movie.language.casefold())
            and (request.max_runtime is None or (movie.runtime_minutes is not None and movie.runtime_minutes <= request.max_runtime)))


async def search_names(provider: TmdbClient, store: CatalogStore, request: NameSearchRequest) -> NameSearchResult:
    if not request.query.strip():
        raise ProviderError(422, 'Enter a movie or person name.')
    try:
        async with asyncio.timeout(30):
            return await _search(provider, store, request)
    except TimeoutError:
        raise ProviderError(504, 'Name search took too long. Please try again.') from None
    except (sqlite3.Error, OSError, ValueError):
        raise ProviderError(503, 'Movie metadata could not be saved. Please try again.') from None


async def _search(provider, store, request):
    people, selected, partial, limited = [], None, False, False
    if request.person_id is not None:
        selected, credits = await asyncio.gather(provider.person(request.person_id), provider.person_movie_credits(request.person_id))
        ids = director_movie_ids(credits['crew']) if request.role == 'director' else acting_movie_ids(credits['cast'])
        # Deterministic provider order, bounded pages; never combine crew and cast.
        limited = len(ids) > 2000
        ids = ids[:2000]
        start = (request.page - 1) * 20
        has_more = start + 20 < len(ids)
        ids = ids[start:start + 20]
    else:
        titles, persons = await asyncio.gather(
            provider.search_movie_names(request.query, page=request.page),
            provider.search_person_names(request.query, page=request.page), return_exceptions=True)
        failures = [r for r in (titles, persons) if isinstance(r, Exception)]
        if len(failures) == 2:
            raise failures[0]
        partial = bool(failures)
        ids = [] if isinstance(titles, Exception) else [r.id for r in titles.items]
        people = [] if isinstance(persons, Exception) else persons.items
        valid_pages = [r for r in (titles, persons) if not isinstance(r, Exception)]
        has_more = any(request.page < r.total_pages for r in valid_pages)
        limited = any(r.limited for r in valid_pages)

    async def hydrate(movie_id):
        saved = await asyncio.to_thread(store.get_movie, movie_id)
        if saved is not None and await asyncio.to_thread(store.metadata_is_fresh, movie_id):
            return saved, False, False
        try:
            movie = await provider.movie(movie_id, enrich=True)
        except ProviderError:
            if saved is not None:
                return saved, False, True
            raise
        if movie.id != movie_id or movie.source != 'tmdb':
            raise ProviderError(502, 'Movie identity could not be verified.')
        return movie, True, False

    outcomes = await asyncio.gather(*(hydrate(mid) for mid in ids), return_exceptions=True)
    movies, fresh = [], []
    for result in outcomes:
        if isinstance(result, (sqlite3.Error, OSError, ValueError)):
            raise result
        if isinstance(result, Exception):
            if not isinstance(result, ProviderError):
                raise result
            partial = True
            continue
        movie, fetched, stale = result
        partial |= stale
        movies.append(movie)
        if fetched:
            fresh.append(movie)
    if ids and not movies and all(isinstance(r, ProviderError) and r.status != 404 for r in outcomes):
        # Entire hydration failure is retryable; do not present it as no matches.
        raise ProviderError(502, 'Matching movies could not be loaded. Please try again.')
    # Only fresh fetched records get a new timestamp. Cached/stale records retain theirs.
    if fresh:
        await asyncio.to_thread(store.import_movies, fresh, fetched_at=datetime.now(timezone.utc).isoformat())
    return NameSearchResult(items=[m for m in movies if matches_filters(m, request)], people=people,
                            selected_person=selected, role=request.role, page=request.page,
                            has_more=has_more, partial=partial, limited=limited)
