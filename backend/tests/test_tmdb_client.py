import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from movie_companion.main import app, get_provider, get_detail_provider
from movie_companion.settings import get_settings
from movie_companion.tmdb_client import ProviderError, TmdbClient
from movie_companion.search_suggestions import SuggestionIndex


def details(movie_id=123, **changes):
    return {
        "id": movie_id, "title": "Example Film", "release_date": "2024-03-15",
        "runtime": 112, "original_language": "ko", "genres": [{"id": 18, "name": "Drama"}],
        "poster_path": "/example.jpg", "overview": "An example overview.", "tagline": "",
        "credits": {"cast": [{"name": "Example Actor"}],
                    "crew": [{"name": "Example Director", "job": "Director"}]},
        **changes,
    }


LANGUAGES = [{"iso_639_1": "ko", "english_name": "Korean"}]


def run(handler, check, **options):
    async def scenario():
        async with httpx.AsyncClient(base_url="https://api.themoviedb.org/3",
                                     transport=httpx.MockTransport(handler),
                                     headers={"Authorization": "Bearer synthetic-test-token"}, timeout=8) as http:
            await check(TmdbClient(http, **options))
    asyncio.run(scenario())


def test_detail_composition_cache_and_authentication():
    paths = []
    index = SuggestionIndex()
    def handler(request):
        paths.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer synthetic-test-token"
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json=LANGUAGES)
        assert request.url.params["append_to_response"] == "credits,videos"
        return httpx.Response(200, json=details())

    async def check(provider):
        movie = await provider.movie(123)
        assert movie.source == "tmdb"
        assert movie.language == "Korean"
        assert movie.cast == ["Example Actor"]
        assert movie.director == "Example Director"
        assert movie.cover_url == "https://image.tmdb.org/t/p/w500/example.jpg"
        assert movie.artwork_kind == "poster"
        assert (await provider.movie(123)) == movie
        assert len(paths) == 2
        assert index.suggest("Example Flim").items[0].label == "Example Film"
    run(handler, check, suggestion_index=index)


@pytest.mark.parametrize("poster", [None, "https://untrusted.example/poster.jpg", "/../example.jpg"])
def test_missing_or_untrusted_poster_uses_placeholder(poster):
    def handler(request):
        return httpx.Response(200, json=LANGUAGES if request.url.path.endswith("/languages") else details(
            poster_path=poster, runtime=None, release_date="", credits={"cast": [], "crew": []}))
    async def check(provider):
        movie = await provider.movie(123)
        assert movie.cover_url is None
        assert movie.artwork_kind == "placeholder"
        assert movie.runtime_minutes is None
        assert movie.year is None
        assert movie.director is None
    run(handler, check)


@pytest.mark.parametrize("status, expected", [(401, 503), (403, 503), (429, 503), (500, 502), (404, 404), (302, 502)])
def test_upstream_errors_are_sanitized_and_not_cached(status, expected):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"secret": "synthetic-test-token"})
    async def check(provider):
        for _ in range(2):
            with pytest.raises(ProviderError) as error:
                await provider._get("/movie/123")
            assert error.value.status == expected
            assert "synthetic-test-token" not in str(error.value)
        assert len(calls) == 2
    run(handler, check)


def test_timeout_is_sanitized():
    def handler(request):
        raise httpx.ReadTimeout("synthetic-test-token", request=request)
    async def check(provider):
        with pytest.raises(ProviderError) as error:
            await provider._get("/movie/123")
        assert error.value.status == 504
        assert "synthetic-test-token" not in str(error.value)
    run(handler, check)


def test_invalid_json_is_rejected():
    async def check(provider):
        with pytest.raises(ProviderError) as error:
            await provider._get("/movie/123")
        assert error.value.status == 502
    run(lambda request: httpx.Response(200, text="not json"), check)


def test_wrong_movie_identity_is_rejected():
    def handler(request):
        return httpx.Response(200, json=LANGUAGES if request.url.path.endswith("/languages") else details(999))
    async def check(provider):
        with pytest.raises(ProviderError) as error:
            await provider.movie(123)
        assert error.value.status == 502
    run(handler, check)


def test_cache_expiry_and_size_bound():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={})
    async def check(provider):
        await provider._get("/movie/1")
        await provider._get("/movie/1")
        assert len(paths) == 2  # ttl=0 immediately expires the entry.
        await provider._get("/movie/2")
        await provider._get("/movie/3")
        assert len(provider.cache) == 2
    run(handler, check, ttl=0, cache_size=2)


def test_title_search_filters_hydrated_results():
    def handler(request):
        path = request.url.path
        if path.endswith("/search/movie"):
            assert request.url.params["query"] == "Example"
            return httpx.Response(200, json={"results": [{"id": 123}, {"id": 124}]})
        if path.endswith("/search/person"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/languages"):
            return httpx.Response(200, json=LANGUAGES)
        movie_id = int(path.rsplit("/", 1)[1])
        return httpx.Response(200, json=details(movie_id, runtime=112 if movie_id == 123 else None))
    async def check(provider):
        result = await provider.search(" Example ", "drama", 120, " Korean ")
        assert [movie.id for movie in result.items] == [123]
        assert result.data_source == "tmdb" and result.limited
        assert (await provider.search("Example", None, None, "Martian")).items == []
    run(handler, check)


def test_exact_actor_search_uses_cast_not_crew_credits():
    def handler(request):
        path = request.url.path
        if path.endswith("/search/person"):
            return httpx.Response(200, json={"results": [{"id": 7, "name": "Example Actor", "known_for_department": "Acting"}]})
        if path.endswith("/search/movie"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/person/7/movie_credits"):
            return httpx.Response(200, json={"cast": [{"id": 123, "popularity": 10}], "crew": [{"id": 999}]})
        if path.endswith("/languages"):
            return httpx.Response(200, json=LANGUAGES)
        assert path.endswith("/movie/123")
        return httpx.Response(200, json=details())
    async def check(provider):
        result = await provider.search("example actor", None, None, None)
        assert [movie.id for movie in result.items] == [123]
    run(handler, check)


def test_search_caps_candidates_and_upstream_concurrency():
    active = 0
    maximum = 0
    movie_ids = set()
    async def handler(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.001)
        active -= 1
        path = request.url.path
        if path.endswith("/discover/movie"):
            return httpx.Response(200, json={"results": [{"id": number} for number in range(1, 31)]})
        if path.endswith("/languages"):
            return httpx.Response(200, json=LANGUAGES)
        movie_id = int(path.rsplit("/", 1)[1])
        movie_ids.add(movie_id)
        return httpx.Response(200, json=details(movie_id))
    async def check(provider):
        result = await provider.search("", None, None, None)
        assert len(result.items) == 20
        assert len(movie_ids) == 20
        assert maximum <= 4
    run(handler, check)


def test_search_does_not_hide_provider_failures():
    def handler(request):
        if request.url.path.endswith("/discover/movie"):
            return httpx.Response(200, json={"results": [{"id": 123}]})
        return httpx.Response(503, json={})
    async def check(provider):
        with pytest.raises(ProviderError):
            await provider.search("", None, None, None)
    run(handler, check)


def test_live_mode_without_token_returns_safe_configuration_error(monkeypatch):
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "tmdb")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/search")
        assert response.status_code == 503
        assert "TMDB_READ_TOKEN" in response.json()["detail"]
        assert client.get("/api/health").json()["data_source"] == "tmdb"


def test_routes_use_live_provider_and_keep_unknown_metadata():
    class FakeProvider:
        async def movie(self, movie_id):
            from movie_companion.schemas import Movie
            return Movie(id=movie_id, title="Live Example", language="Unknown", genres=[], cast=[],
                         overview="", tagline="", source="tmdb", artwork_kind="placeholder")
        async def search(self, *args):
            from movie_companion.schemas import MovieSearchResponse
            return MovieSearchResponse(items=[await self.movie(123)], total=1, data_source="tmdb", limited=True)
    app.dependency_overrides[get_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_detail_provider] = lambda: FakeProvider()
    try:
        with TestClient(app) as client:
            data = client.get("/api/search").json()
            assert data["data_source"] == "tmdb"
            assert data["items"][0]["runtime_minutes"] is None
            assert client.get("/api/movies/123").json()["title"] == "Live Example"
    finally:
        app.dependency_overrides.pop(get_provider, None)
        app.dependency_overrides.pop(get_detail_provider, None)


def test_enriched_metadata_retains_language_and_maps_keywords_alternative_titles():
    async def check():
        def handler(request):
            if request.url.path.endswith('/languages'):
                return httpx.Response(200, json=LANGUAGES)
            assert request.url.params['append_to_response'] == 'credits,keywords,alternative_titles'
            return httpx.Response(200, json=details(keywords={'keywords': [{'id': 1, 'name': 'superhero'}]}, alternative_titles={'titles': [{'title': 'Alternate Film'}]}))
        async with httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(handler)) as client:
            movie = await TmdbClient(client).movie(123, enrich=True)
            assert movie.keywords == ['superhero']
            assert movie.alternative_titles == ['Alternate Film']
            assert movie.language == 'Korean'
    asyncio.run(check())
