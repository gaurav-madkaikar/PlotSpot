"""One search interface: identity, constraints, supported semantic ranking, pages."""
import asyncio
import math
import re
import hashlib
import json
import logging
from time import perf_counter
from pydantic import BaseModel, Field

from .catalog import load_catalog
from .schemas import MovieSearchResponse
from .search_intent import interpret, synopsis_support, theme_support
from .search_suggestions import SuggestionIndex
from .search_text import normalize_search_text
from .semantic_catalog import read_index
from .semantic_search import DiscoveryError, SemanticSearch, eligible
from .vector_math import cosine_similarity


class CatalogQuery(BaseModel):
    query: str = Field(default='', max_length=300)
    genre: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    max_runtime: int | None = Field(default=None, ge=1, le=600)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=40)


def identity_matches(movies, query):
    needle = normalize_search_text(query)
    directing = bool(re.match(r'^(?:movies? directed by|films? directed by|directed by) ', needle))
    acting = bool(re.match(r'^(?:movies? starring|films? starring|starring) ', needle))
    needle = re.sub(r'^(?:movies? with|films? with|movies? starring|films? starring|movies? directed by|films? directed by|directed by|starring) ', '', needle)
    if not needle:
        return []
    matches = []
    for movie in movies:
        titles = [normalize_search_text(t) for t in [movie.title, *movie.alternative_titles]]
        title = titles[0]
        cast = [normalize_search_text(c) for c in movie.cast]
        directors = [normalize_search_text(c.strip()) for c in (movie.director or "").split(",")]
        people = directors if directing else cast if acting else cast + directors
        if not (directing or acting) and needle in titles:
            priority = 0
        elif needle in people:
            priority = 1
        elif not (directing or acting) and any(needle in t for t in titles):
            priority = 2
        elif any(needle in c for c in people):
            priority = 3
        else:
            continue
        matches.append((priority, movie))
    return [m for _, m in sorted(matches, key=lambda pair: (pair[0], pair[1].title.casefold(), pair[1].id))]


async def search_catalog(service: SemanticSearch, request: CatalogQuery, *, demo=False, identity_movies=None) -> MovieSearchResponse:
    started = perf_counter()
    if demo:
        movies, vectors, prepared_at = list(load_catalog()), None, None
    else:
        try:
            index = await service.catalog_snapshot()
        except (OSError, ValueError):
            raise DiscoveryError(503, 'The movie collection is unavailable. Please try again shortly.') from None
        movies, vectors, prepared_at = index.movies, dict(zip((m.id for m in index.movies), index.vectors)), index.prepared_at
    query = request.query.strip()
    intent = interpret(query)
    # A canonical title/cast can contain genre words; identity takes precedence
    # except for a pure genre request such as "romance".
    identity_pool = list({m.id: m for m in [*movies, *(identity_movies or [])]}.values())
    identities = identity_matches(identity_pool, query) if query and not intent.genre_only else []
    constrained = [m for m in movies if eligible(m, request)]
    if not identities and service.hybrid is not None and not demo:
        # Explicit UI filters/exclusions are strict; descriptive genre words are preferences.
        constrained = [m for m in constrained if not intent.excluded & set(m.genres) and (not intent.genre_only or intent.required <= set(m.genres))]
    elif not identities:
        constrained = [m for m in constrained if intent.required <= set(m.genres) and not intent.excluded & set(m.genres) and theme_support(m.title, m.overview, intent)]
    kind, corrected = 'browse', None
    if identities:
        ranked, kind = [m for m in identities if eligible(m, request)], 'title_cast'
    elif query and not intent.genre_only:
        suggestions = SuggestionIndex(movies).suggest(query, threshold=0.85)
        if suggestions.items and len(normalize_search_text(query).split()) <= 5:
            best = suggestions.items[0]
            ids = set(best.movie_ids)
            ranked, kind, corrected = [m for m in constrained if m.id in ids], 'typo', best.label
        elif service.hybrid is not None and not demo:
            kind = 'semantic'
            ids = await service.hybrid.rank(service, constrained, vectors, query, index.fingerprint)
            by_id = {m.id: m for m in constrained}
            ranked = [by_id[mid] for mid in ids]
        else:
            # Conservative lexical evidence gate: never fill every nearest-neighbor
            # slot when saved metadata provides no support for the request.
            supported = [m for m in constrained if synopsis_support(m.overview, intent) > 0 or (not intent.terms and (intent.required_themes or intent.excluded_themes))]
            kind = 'semantic'
            if vectors and supported:
                vector = await service.query_vector(query, len(next(iter(vectors.values()))))
                try:
                    ranked = sorted(supported, key=lambda m: (-cosine_similarity(vector, vectors[m.id]), -synopsis_support(m.overview, intent), m.id))
                except ValueError:
                    raise DiscoveryError(502, 'Search results could not be verified. Please try again.') from None
            else:
                # Offline demo is lexical synopsis ranking, clearly marked demo.
                ranked = sorted(supported, key=lambda m: (-synopsis_support(m.overview,intent), m.id))
    else:
        ranked = constrained
        kind = 'genre' if query else 'browse'
    applied_genres = sorted(intent.required) if not identities and (intent.genre_only or service.hybrid is None or demo) else []
    if request.genre:
        canonical = next((g for m in movies for g in m.genres if g.casefold() == request.genre.strip().casefold()), None)
        if canonical and canonical not in applied_genres:
            applied_genres.append(canonical)
    total = len(ranked)
    start = (request.page - 1) * request.page_size
    trace = service.hybrid.last_trace if service.hybrid is not None and kind == 'semantic' and not demo else None
    logging.getLogger('uvicorn.error').info(json.dumps({
        'event': 'movie_search', 'query_hash': hashlib.sha256(query.encode()).hexdigest()[:16],
        'catalog_fingerprint': index.fingerprint if not demo else 'demo', 'match_type': kind,
        'candidate_count': len(trace['candidate_ids']) if trace else None,
        'total': total, 'page': request.page, 'latency_ms': round((perf_counter() - started) * 1000),
    }))
    return MovieSearchResponse(items=ranked[start:start+request.page_size], total=total,
        data_source='demo' if demo else 'tmdb', limited=True, page=request.page,
        page_size=request.page_size, total_pages=math.ceil(total/request.page_size),
        indexed_movies=len(movies), match_type=kind, matched_query=corrected, prepared_at=prepared_at, applied_genres=applied_genres)
