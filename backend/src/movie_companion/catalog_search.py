"""Deterministic metadata keyword search. No model, vector index or network access."""
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, Field

from .schemas import Movie, MovieSearchResponse
from .movie_ratings import movie_rating, rating_sort_key
from .search_suggestions import SuggestionIndex
from .search_text import normalize_search_text


class CatalogQuery(BaseModel):
    include_adult: bool = True
    query: str = Field(default='', max_length=300)
    genre: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    max_runtime: int | None = Field(default=None, ge=1, le=600)
    sort_by: Literal['trusted', 'rating'] = 'trusted'
    min_rating: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=40)


FILLER = frozenset('a an the and of to in on at for by with about movie movies film films'.split())


def query_identity(query):
    needle = normalize_search_text(query)
    role = 'director' if re.match(r'^(?:movies? |films? )?directed by ', needle) else 'actor' if re.match(r'^(?:movies? |films? )?starring ', needle) else None
    needle = re.sub(r'^(?:movies? with|films? with|movies? starring|films? starring|movies? directed by|films? directed by|directed by|starring) ', '', needle)
    return needle, role


def identity_priority(movie, needle, role=None, *, record=None):
    titles = record.titles if record else [normalize_search_text(t) for t in [movie.title, *movie.alternative_titles]]
    cast = record.cast if record else [normalize_search_text(t) for t in movie.cast]
    directors = record.directors if record else [normalize_search_text(t) for t in (movie.director or '').split(',')]
    people = directors if role == 'director' else cast if role == 'actor' else cast + directors
    if not role and needle in titles:
        return 0
    if needle in people:
        return 1
    if not role and any(' '+needle in ' '+title for title in titles):
        return 2
    if any(' '+needle in ' '+person for person in people):
        return 3
    return None


def identity_matches(movies, query):
    needle, role = query_identity(query)
    if not needle:
        return []
    pairs = [(identity_priority(m, needle, role), m) for m in movies]
    return [m for priority, m in sorted((p for p in pairs if p[0] is not None),
            key=lambda pair: identity_sort_key(pair[1], needle, role))]


def identity_sort_key(movie, needle, role=None, *, fallback=4, record=None, sort_by='trusted'):
    """Prefer short canonical title completions over incidental words or aliases."""
    priority = identity_priority(movie, needle, role, record=record) if needle else None
    title = record.titles[0] if record else normalize_search_text(movie.title)
    completion = bool(needle) and not role and priority in (0, 2) and title.startswith(needle)
    return (priority if priority is not None else fallback,
            0 if completion else 1, *rating_sort_key(movie, sort_by),
            len(title) - len(needle) if completion else 0, movie.title.casefold(), movie.id)


def eligible(movie, request):
    return ((request.include_adult or movie.adult is not True)
            and (not request.genre or request.genre.strip().casefold() in {g.casefold() for g in movie.genres})
            and (not request.language or request.language.strip().casefold() == movie.language.casefold())
            and (request.max_runtime is None or (movie.runtime_minutes is not None and movie.runtime_minutes <= request.max_runtime))
            and (request.min_rating is None or (movie_rating(movie)[0] is not None and movie_rating(movie)[0] >= request.min_rating)))


def edit_distance(left, right):
    """Bounded words only; adjacent transpositions count as one typo."""
    rows = [list(range(len(right) + 1))]
    for i, char in enumerate(left, 1):
        row = [i]
        for j, other in enumerate(right, 1):
            value = min(rows[-1][j] + 1, row[-1] + 1, rows[-1][j-1] + (char != other))
            if i > 1 and j > 1 and char == right[j-2] and left[i-2] == other:
                value = min(value, rows[-2][j-2] + 1)
            row.append(value)
        rows.append(row)
    return rows[-1][-1]


def correct_terms(terms, vocabulary):
    corrected = []
    for term in terms:
        if term in vocabulary:
            corrected.append(term)
            continue
        # Short/long/numeric tokens are too ambiguous or expensive to auto-correct.
        if not 4 <= len(term) <= 32 or not term.isalpha():
            return None
        limit = 1 if len(term) <= 5 else 2
        choices = []
        for word in vocabulary:
            if not 4 <= len(word) <= 34 or not word.isalpha() or abs(len(word)-len(term)) > limit:
                continue
            distance = edit_distance(term, word)
            similarity = 1 - distance / max(len(term), len(word))
            if distance <= limit and similarity >= .8:
                choices.append((distance, -similarity, word))
        choices.sort()
        if not choices or (len(choices) > 1 and choices[0][:2] == choices[1][:2]):
            return None  # Equally plausible corrections require a user choice.
        corrected.append(choices[0][2])
    return corrected


def metadata_fields(movie):
    return [normalize_search_text(text) for text in [movie.title, *movie.alternative_titles,
        *movie.cast, movie.director or '', movie.overview, *movie.genres]]


@dataclass(frozen=True)
class SearchRecord:
    movie: Movie
    titles: tuple[str, ...]
    cast: tuple[str, ...]
    directors: tuple[str, ...]
    fields: tuple[str, ...]
    words: frozenset[str]


class PreparedCatalog:
    """Normalize once per catalog revision, not once per typed query."""
    def __init__(self, movies):
        self._non_adult = None
        self.movies = tuple({m.id: m for m in movies}.values())
        def prepare(m):
            fields = tuple(metadata_fields(m))
            return SearchRecord(m,
            tuple(normalize_search_text(t) for t in [m.title, *m.alternative_titles]),
            tuple(normalize_search_text(t) for t in m.cast),
            tuple(normalize_search_text(t) for t in (m.director or '').split(',')),
            fields, frozenset(t for field in fields for t in field.split()))
        self.records = tuple(prepare(m) for m in self.movies)
        self.by_id = {r.movie.id: r for r in self.records}
        self.vocabulary = frozenset(t for r in self.records for t in r.words)
        self.suggestions = SuggestionIndex(self.movies, capacity=max(1500, len(self.movies)))


    def filtered(self, include_adult):
        if include_adult or not any(m.adult is True for m in self.movies):
            return self
        if self._non_adult is None:
            self._non_adult = PreparedCatalog(m for m in self.movies if m.adult is not True)
        return self._non_adult


def search_catalog(movies, request: CatalogQuery, *, demo=False, paginate=True, correct_typos=True):
    started = perf_counter()
    # Freshly hydrated records are part of the same metadata corpus, with no indexing wait.
    prepared = movies if isinstance(movies, PreparedCatalog) else PreparedCatalog(movies)
    prepared = prepared.filtered(request.include_adult)
    movies = prepared.movies
    query = request.query.strip()
    needle, role = query_identity(query)
    records = prepared.records
    terms = [t for t in needle.split() if t not in FILLER]
    vocabulary = prepared.vocabulary
    identities = bool(needle) and any(identity_priority(r.movie, needle, role, record=r) is not None for r in records)
    corrected, kind = None, 'browse' if not needle else 'keyword'
    if correct_typos and needle and not identities:
        suggestions = prepared.suggestions.suggest(needle, threshold=.85)
        if role:
            suggestions.items = [s for s in suggestions.items if s.kind == role]
        # Different localized aliases of one movie are the same verified identity.
        best = [s for s in suggestions.items if s.score == suggestions.items[0].score] if suggestions.items else []
        labels = {s.label for s in best}
        same_movie = bool(best) and all(s.kind == 'movie' and len(s.movie_ids) == 1
            and s.movie_ids == best[0].movie_ids for s in best)
        if len(labels) == 1 or same_movie:
            corrected = next(m.title for m in movies if m.id == best[0].movie_ids[0]) if same_movie else best[0].label
            needle, _ = query_identity(corrected)
            terms = [t for t in needle.split() if t not in FILLER]
            kind = 'typo'
        elif not suggestions.items and not role and terms and any(t not in vocabulary for t in terms):
            fixed = correct_terms(terms, vocabulary)
            if fixed and fixed != terms:
                terms, corrected, kind = fixed, ' '.join(fixed), 'typo'
    if identities:
        kind = 'title_cast'
    ranked = []
    for record in records:
        movie, fields = record.movie, record.fields
        if not eligible(movie, request):
            continue
        if not needle:
            ranked.append((0, movie))
            continue
        priority = identity_priority(movie, needle, role, record=record)
        if priority is not None:
            ranked.append((priority, movie))
        elif not role and terms and set(terms) <= record.words:
            # All terms need actual metadata support, even when spread across fields.
            ranked.append((4 if any(needle in field for field in fields) else 5, movie))
    ranked.sort(key=lambda pair: identity_sort_key(pair[1], needle, role, fallback=pair[0], record=prepared.by_id[pair[1].id], sort_by=request.sort_by))
    ranked = [m for _, m in ranked]
    total = len(ranked)
    start = (request.page-1)*request.page_size
    applied = [request.genre] if request.genre else []
    logging.getLogger('uvicorn.error').info(json.dumps({'event':'movie_search',
        'query_hash':hashlib.sha256(query.encode()).hexdigest()[:16], 'match_type':kind,
        'total':total,'page':request.page,'latency_ms':round((perf_counter()-started)*1000)}))
    return MovieSearchResponse(items=ranked[start:start+request.page_size] if paginate else ranked,total=total,
        data_source='demo' if demo else 'tmdb',limited=True,page=request.page,page_size=request.page_size,
        total_pages=math.ceil(total/request.page_size),indexed_movies=len(movies),match_type=kind,
        matched_query=corrected,applied_genres=applied)
