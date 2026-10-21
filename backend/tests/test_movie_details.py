import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from movie_companion.catalog import load_catalog
from movie_companion.schemas import MovieMetadata
from movie_companion.catalog_store import CatalogStore
from movie_companion.main import app, get_catalog_store, get_detail_provider
from movie_companion.movie_details import load_movie_details
from movie_companion.tmdb_client import ProviderError


def movie():
    return load_catalog()[0].model_copy(update={"source": "tmdb", "detail_metadata": MovieMetadata(presentation_version=1)})


class Provider:
    def __init__(self, result=None, error=None):
        self.result = result or movie()
        self.error = error
        self.calls = 0

    async def movie(self, movie_id):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_fresh_saved_movie_never_calls_provider(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_movie(movie(), fetched_at=datetime.now(timezone.utc).isoformat())
    provider = Provider(error=AssertionError("Network must not run"))
    assert asyncio.run(load_movie_details(movie().id, store=store, provider=provider)) == movie()
    assert provider.calls == 0


def test_missing_record_is_fetched_saved_and_reused_after_restart(tmp_path):
    path = tmp_path / "catalog.db"
    provider = Provider()
    assert asyncio.run(load_movie_details(movie().id, store=CatalogStore(path), provider=provider)) == movie()
    assert asyncio.run(load_movie_details(movie().id, store=CatalogStore(path), provider=provider)) == movie()
    assert provider.calls == 1


@pytest.mark.parametrize("status", [404, 502, 503, 504])
def test_provider_failure_preserves_last_good_stale_record(tmp_path, status):
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_movie(movie(), fetched_at="2000-01-01T00:00:00+00:00")
    provider = Provider(error=ProviderError(status, "Unavailable"))
    assert asyncio.run(load_movie_details(movie().id, store=store, provider=provider)) == movie()
    assert not store.metadata_is_fresh(movie().id)
    assert provider.calls == 1


def test_stale_refresh_preserves_richer_fields(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_movie(movie(), fetched_at="2000-01-01T00:00:00+00:00")
    result = movie().model_copy(update={"cast": [], "overview": "New synopsis"})
    refreshed = asyncio.run(load_movie_details(movie().id, store=store, provider=Provider(result)))
    assert refreshed.overview == "New synopsis" and refreshed.cast == movie().cast
    assert store.metadata_is_fresh(movie().id)


def test_invalid_provider_id_is_not_persisted(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    with pytest.raises(ProviderError) as error:
        asyncio.run(load_movie_details(movie().id, store=store, provider=Provider(movie().model_copy(update={"id": 123}))))
    assert error.value.status == 502
    assert store.get_movie(movie().id) is None and store.get_movie(123) is None


def test_missing_record_without_provider_is_recoverable(tmp_path):
    with pytest.raises(ProviderError) as error:
        asyncio.run(load_movie_details(movie().id, store=CatalogStore(tmp_path / "catalog.db"), provider=None))
    assert error.value.status == 503


def test_api_reads_saved_movie_without_token_or_provider(tmp_path, monkeypatch):
    from movie_companion.settings import get_settings
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "tmdb")
    get_settings.cache_clear()
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_movie(movie(), fetched_at=datetime.now(timezone.utc).isoformat())
    app.dependency_overrides[get_catalog_store] = lambda: store
    app.dependency_overrides[get_detail_provider] = lambda: None
    try:
        client = TestClient(app)
        response = client.get(f"/api/movies/{movie().id}")
        assert response.status_code == 200
        assert response.json()["title"] == movie().title
        assert client.get("/api/movies/999999999").status_code == 503
    finally:
        app.dependency_overrides.pop(get_catalog_store, None)
        app.dependency_overrides.pop(get_detail_provider, None)
