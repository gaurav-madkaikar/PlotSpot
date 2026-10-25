"""Read-only TMDB provider with bounded work and sanitized failures."""

import asyncio
import re
from collections import OrderedDict
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from .schemas import Movie, MovieSearchResponse
from .movie_metadata import map_metadata
from .movie_preview import map_movie_preview
from .movie_extras import watch_options, watch_regions, related_movies
from .tmdb import map_tmdb_details
from .search_suggestions import SuggestionIndex
from .name_discovery import MovieNameCandidate, PersonNameCandidate, NamePage, name_query, name_page


class ProviderError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


class TmdbClient:
    def __init__(self, http: httpx.AsyncClient, *, ttl: float = 600, cache_size: int = 256,
                 suggestion_index: SuggestionIndex | None = None):
        self.http = http
        self.ttl = ttl
        self.cache_size = cache_size
        self.cache: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self.slots = asyncio.Semaphore(4)
        self.suggestion_index = suggestion_index
        self.preview_config_slot = asyncio.Lock()

    async def _get(self, path: str, **params: Any) -> Any:
        key = (path, tuple(sorted(params.items())))
        cached = self.cache.get(key)
        if cached and cached[0] > monotonic():
            self.cache.move_to_end(key)
            return cached[1]
        self.cache.pop(key, None)
        try:
            async with self.slots:
                # A queued request may have been filled by another caller.
                cached = self.cache.get(key)
                if cached and cached[0] > monotonic():
                    self.cache.move_to_end(key)
                    return cached[1]
                response = await self.http.get(path, params={"language": "en-US", **params})
            if response.status_code == 404:
                raise ProviderError(404, "Movie is unavailable from TMDB")
            if response.status_code in {401, 403}:
                raise ProviderError(503, "TMDB credentials were rejected; check backend configuration")
            if response.status_code == 429:
                raise ProviderError(503, "TMDB request limit reached; try again later")
            if not response.is_success:
                raise ProviderError(502, "TMDB is temporarily unavailable")
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise ValueError("Unexpected response shape")
        except httpx.TimeoutException:
            raise ProviderError(504, "TMDB took too long to respond") from None
        except (httpx.HTTPError, ValueError):
            raise ProviderError(502, "TMDB returned an unavailable or invalid response") from None
        self.cache[key] = (monotonic() + self.ttl, payload)
        self.cache.move_to_end(key)
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return payload

    @staticmethod
    def _records(payload: Any, key: str) -> list[dict]:
        if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
            raise ProviderError(502, "TMDB returned incomplete movie data")
        records = payload[key]
        if not all(isinstance(item, dict) for item in records):
            raise ProviderError(502, "TMDB returned invalid movie data")
        return records

    async def search_movie_names(self, query: str, *, page: int = 1) -> NamePage[MovieNameCandidate]:
        needle = name_query(query, page)
        payload = await self._get("/search/movie", query=needle, include_adult="true", page=page)
        try:
            return name_page(payload, page, MovieNameCandidate)
        except ValueError:
            raise ProviderError(502, "TMDB returned invalid movie-name results") from None

    async def search_person_names(self, query: str, *, page: int = 1) -> NamePage[PersonNameCandidate]:
        needle = name_query(query, page)
        payload = await self._get("/search/person", query=needle, include_adult="true", page=page)
        try:
            return name_page(payload, page, PersonNameCandidate)
        except ValueError:
            raise ProviderError(502, "TMDB returned invalid person-name results") from None

    async def person(self, person_id: int) -> PersonNameCandidate:
        if type(person_id) is not int or person_id <= 0:
            raise ValueError("Person ID must be a positive integer")
        payload = await self._get(f"/person/{person_id}")
        try:
            person = PersonNameCandidate.model_validate(payload)
            if person.id != person_id:
                raise ValueError("Mismatched person")
            return person
        except ValueError:
            raise ProviderError(502, "TMDB returned invalid person identity") from None

    async def person_movie_credits(self, person_id: int) -> dict[str, list[dict]]:
        if type(person_id) is not int or person_id <= 0:
            raise ValueError("Person ID must be a positive integer")
        payload = await self._get(f"/person/{person_id}/movie_credits")
        if not isinstance(payload, dict) or type(payload.get("id")) is not int or payload["id"] != person_id:
            raise ProviderError(502, "TMDB returned mismatched person credits")
        cast, crew = self._records(payload, "cast"), self._records(payload, "crew")
        if len(cast) + len(crew) > 10_000:
            raise ProviderError(502, "TMDB movie credits exceed the work bound")
        for record in cast + crew:
            if type(record.get("id")) is not int or record["id"] <= 0 or type(record.get("adult", False)) is not bool:
                raise ProviderError(502, "TMDB returned invalid movie-credit identity")
        if any(not isinstance(record.get("job"), str) or not record["job"].strip() for record in crew):
            raise ProviderError(502, "TMDB returned invalid crew roles")
        return {"cast": cast, "crew": crew}

    async def watch_options(self, movie_id: int, country: str):
        return watch_options(await self._get(f"/movie/{movie_id}/watch/providers"), movie_id, country)

    async def watch_regions(self):
        return watch_regions(await self._get("/watch/providers/regions"))

    async def related_movies(self, movie_id: int):
        return related_movies(await self._get(f"/movie/{movie_id}/recommendations", page=1), movie_id)

    async def movie_preview(self, movie_id: int, *, candidate=None, require_runtime=False) -> Movie:
        if type(movie_id) is not int or movie_id <= 0 or (candidate is not None and candidate.id != movie_id):
            raise ValueError('Invalid movie preview identity')
        supplied = candidate is not None and {'overview', 'original_language', 'genre_ids', 'poster_path'} <= candidate.model_fields_set
        try:
            if supplied and not require_runtime:
                # One shared config read instead of a movie-details request per title tile.
                async with self.preview_config_slot:
                    languages, genres = await asyncio.gather(self._get('/configuration/languages'), self._get('/genre/movie/list'))
                genre_names = {g['id']: g['name'] for g in self._records(genres, 'genres')}
                payload = {**candidate.model_dump(), 'genres': [{'name': genre_names[g]} for g in candidate.genre_ids if g in genre_names]}
            else:
                payload, languages = await asyncio.gather(self._get(f'/movie/{movie_id}'), self._get('/configuration/languages'))
            if not isinstance(languages, list):
                raise ValueError('Invalid movie languages')
            return map_movie_preview(payload, movie_id, languages)
        except (ValueError, TypeError, KeyError):
            raise ProviderError(502, 'TMDB returned invalid movie preview metadata') from None

    async def movie(self, movie_id: int, *, enrich: bool = False) -> Movie:
        details, languages = await asyncio.gather(
            self._get(f"/movie/{movie_id}", append_to_response="credits,keywords,alternative_titles" if enrich else "credits,videos"),
            self._get("/configuration/languages"),
        )
        try:
            mapped = map_tmdb_details(details)
            if mapped.id != movie_id:
                raise ValueError("Mismatched identity")
            if not isinstance(languages, list):
                raise ValueError("Invalid languages")
            names = {item["iso_639_1"]: item["english_name"] for item in languages}
            cast = self._records(details.get("credits"), "cast")
            crew = self._records(details.get("credits"), "crew")
            directors = list(dict.fromkeys(item["name"] for item in crew if item.get("job") == "Director"))
            poster = mapped.poster_path
            # Only a TMDB image path can become a poster URL.
            if poster and not re.fullmatch(r"/[A-Za-z0-9_-]+\.(?:jpg|png|webp)", poster):
                poster = None
            keywords, alternative_titles = [], []
            if enrich:
                def metadata_names(records, key):
                    values = [r.get(key) for r in records]
                    if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in values):
                        raise ValueError('Invalid search metadata')
                    return list(dict.fromkeys(v.strip() for v in values))
                keywords = metadata_names(self._records(details.get('keywords'), 'keywords'), 'name')[:50]
                alternative_titles = metadata_names(self._records(details.get('alternative_titles'), 'titles'), 'title')[:30]
                original = details.get('original_title')
                if isinstance(original, str) and original.strip() and original != mapped.title:
                    alternative_titles = list(dict.fromkeys([original, *alternative_titles]))[:30]
            movie = Movie(
                id=mapped.id, title=mapped.title, year=mapped.year,
                runtime_minutes=mapped.runtime_minutes,
                language=names.get(mapped.original_language, mapped.original_language or "Unknown"),
                genres=mapped.genres, director=", ".join(directors) or None,
                cast=list(dict.fromkeys(item["name"] for item in cast))[:12],
                overview=details.get("overview") or "", tagline=details.get("tagline") or "",
                cover_url=f"https://image.tmdb.org/t/p/w500{poster}" if poster else None,
                keywords=keywords, alternative_titles=alternative_titles,
                detail_metadata=map_metadata(details, cast, crew, presentation=not enrich),
                adult=details.get("adult"),
                source="tmdb", artwork_kind="poster" if poster else "placeholder",
            )
            if self.suggestion_index is not None:
                self.suggestion_index.remember(movie)
            return movie
        except (KeyError, TypeError, AttributeError, ValueError, ValidationError):
            raise ProviderError(502, "TMDB returned incomplete movie data") from None

    async def search(self, query: str, genre: str | None, max_runtime: int | None,
                     language: str | None) -> MovieSearchResponse:
        try:
            async with asyncio.timeout(30):
                return await self._search(query, genre, max_runtime, language)
        except TimeoutError:
            raise ProviderError(504, "Movie search took too long; try a more specific query") from None

    async def _search(self, query: str, genre: str | None, max_runtime: int | None,
                      language: str | None) -> MovieSearchResponse:
        needle = query.strip()
        if needle:
            titles, people = await asyncio.gather(
                self._get("/search/movie", query=needle, include_adult="true", page=1),
                self._get("/search/person", query=needle, include_adult="true", page=1),
            )
            candidates = self._records(titles, "results")
            actors = [person for person in self._records(people, "results")
                      if person.get("known_for_department") == "Acting"
                      and str(person.get("name", "")).casefold() == needle.casefold()]
            # Do not guess when two people have the same name.
            if len(actors) == 1:
                actor_id = actors[0].get("id")
                if not isinstance(actor_id, int) or isinstance(actor_id, bool) or actor_id <= 0:
                    raise ProviderError(502, "TMDB returned invalid actor data")
                credits = await self._get(f"/person/{actor_id}/movie_credits")
                appearances = self._records(credits, "cast")
                appearances.sort(key=lambda movie: movie.get("popularity") or 0, reverse=True)
                candidates = appearances[:20] + candidates
        else:
            candidates = self._records(await self._get(
                "/discover/movie", include_adult="true", include_video="false", page=1,
                sort_by="popularity.desc"), "results")
        ids: list[int] = []
        for item in candidates:
            movie_id = item.get("id")
            if not isinstance(movie_id, int) or isinstance(movie_id, bool) or movie_id <= 0:
                raise ProviderError(502, "TMDB returned invalid movie identity")
            if movie_id not in ids:
                ids.append(movie_id)
            if len(ids) == 20:
                break
        if ids:
            # Resolve the shared language lookup once before parallel hydration.
            await self._get("/configuration/languages")
        outcomes = await asyncio.gather(*(self.movie(movie_id) for movie_id in ids), return_exceptions=True)
        movies = []
        for result in outcomes:
            if isinstance(result, ProviderError) and result.status == 404:
                continue  # A film can disappear between discovery and detail retrieval.
            if isinstance(result, Exception):
                if isinstance(result, ProviderError):
                    raise result
                raise ProviderError(502, "TMDB returned invalid search data") from None
            movies.append(result)
        genre_filter = (genre or "").strip().casefold()
        language_filter = (language or "").strip().casefold()
        movies = [movie for movie in movies
                  if (not genre_filter or genre_filter in {name.casefold() for name in movie.genres})
                  and (max_runtime is None or (movie.runtime_minutes is not None and movie.runtime_minutes <= max_runtime))
                  and (not language_filter or language_filter == movie.language.casefold())]
        return MovieSearchResponse(items=movies, total=len(movies), data_source="tmdb", limited=True)
