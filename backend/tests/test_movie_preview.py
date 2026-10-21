import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.movie_details import load_movie_details
from movie_companion.name_discovery import MovieNameCandidate
from movie_companion.schemas import MovieMetadata
from movie_companion.tmdb_client import ProviderError, TmdbClient


def candidate(mid=123, **changes):
    return MovieNameCandidate(id=mid, title='Example Film', release_date='2020-05-01',
        adult=True, overview='A coastal mystery.', original_language='en', genre_ids=[18],
        poster_path='/film.jpg', **changes)


def run(handler, check):
    async def scenario():
        async with httpx.AsyncClient(base_url='https://api.themoviedb.org/3', transport=httpx.MockTransport(handler)) as http:
            await check(TmdbClient(http))
    asyncio.run(scenario())


def test_title_tiles_share_configuration_without_individual_details_reads():
    paths = []
    async def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/languages'):
            return httpx.Response(200, json=[{'iso_639_1': 'en', 'english_name': 'English'}])
        assert request.url.path.endswith('/genre/movie/list')
        return httpx.Response(200, json={'genres': [{'id': 18, 'name': 'Drama'}]})
    async def check(provider):
        movies = await asyncio.gather(*[provider.movie_preview(mid, candidate=candidate(mid)) for mid in range(1, 21)])
        assert len(paths) == 2
        assert all(m.language == 'English' and m.genres == ['Drama'] and m.adult is True for m in movies)
        assert movies[0].cover_url == 'https://image.tmdb.org/t/p/w500/film.jpg'
        assert movies[0].cast == [] and movies[0].detail_metadata is None and movies[0].runtime_minutes is None
    run(handler, check)


def test_runtime_or_person_preview_fetches_only_top_level_details():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        assert 'append_to_response' not in request.url.params
        if request.url.path.endswith('/languages'):
            return httpx.Response(200, json=[{'iso_639_1': 'en', 'english_name': 'English'}])
        return httpx.Response(200, json={'id': 123, 'title': 'Example Film', 'runtime': 98,
             'genres': [{'name': 'Drama'}], 'original_language': 'en', 'overview': 'A coastal mystery.'})
    async def check(provider):
        runtime = await provider.movie_preview(123, candidate=candidate(), require_runtime=True)
        person = await provider.movie_preview(123)
        assert runtime.runtime_minutes == 98 and runtime == person
        assert paths == ['/3/movie/123', '/3/configuration/languages']
    run(handler, check)


@pytest.mark.parametrize('payload', [{'id': 999, 'title': 'Wrong film'}, {'id': 123, 'title': 'Invalid', 'runtime': -1}])
def test_invalid_preview_cannot_establish_movie_identity(payload):
    def handler(request):
        return httpx.Response(200, json=[] if request.url.path.endswith('/languages') else payload)
    async def check(provider):
        with pytest.raises(ProviderError):
            await provider.movie_preview(123)
    run(handler, check)


def test_preview_cannot_refresh_or_replace_existing_full_details(tmp_path):
    store = CatalogStore(tmp_path / 'movies.db')
    old = load_catalog()[0].model_copy(update={'source': 'tmdb', 'detail_metadata': MovieMetadata(presentation_version=1)})
    store.import_movies([old], fetched_at='2000-01-01T00:00:00+00:00')
    incoming = old.model_copy(update={'detail_metadata': None, 'cast': [], 'director': None, 'title': 'Preview'})
    store.import_movies([incoming], fetched_at=datetime.now(timezone.utc).isoformat(), preview=True)
    assert store.get_movie(old.id) == old and not store.metadata_is_fresh(old.id)


def test_opening_a_saved_tile_still_fetches_full_presentation(tmp_path):
    store = CatalogStore(tmp_path / 'movies.db')
    full = load_catalog()[0].model_copy(update={'source': 'tmdb', 'detail_metadata': MovieMetadata(presentation_version=1)})
    preview = full.model_copy(update={'detail_metadata': None, 'cast': [], 'director': None})
    store.import_movies([preview], fetched_at=datetime.now(timezone.utc).isoformat(), preview=True)
    calls = []
    class Provider:
        async def movie(self, movie_id):
            calls.append(movie_id)
            return full
    assert asyncio.run(load_movie_details(full.id, store=store, provider=Provider())) == full
    assert calls == [full.id]
