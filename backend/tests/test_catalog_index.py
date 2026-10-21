from concurrent.futures import ThreadPoolExecutor

import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_index import SavedCatalogIndex
from movie_companion.catalog_search import CatalogQuery, PreparedCatalog, search_catalog
from movie_companion.catalog_store import CatalogStore


STAMP = '2026-10-12T10:00:00+00:00'


@pytest.mark.parametrize('query', ['', 'Interstellar', 'Interstell', 'Intersteler', 'Amy Admas', 'Christopher Nolan', 'linguistt', 'hotel', 'zzzzzz'])
def test_prepared_search_matches_uncached_behavior(query):
    movies = load_catalog()
    request = CatalogQuery(query=query)
    assert search_catalog(PreparedCatalog(movies), request) == search_catalog(movies, request)


def test_index_reuses_preparation_and_observes_other_store_same_timestamp_writes(tmp_path, monkeypatch):
    store = CatalogStore(tmp_path / 'movies.db')
    movie = load_catalog()[0].model_copy(update={'source': 'tmdb'})
    store.import_movies([movie], fetched_at=STAMP)
    original = store.identity_movies
    reads = []
    def counted():
        reads.append(1)
        return original()
    monkeypatch.setattr(store, 'identity_movies', counted)
    index = SavedCatalogIndex(store)
    first = index.get()
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert all(snapshot is first for snapshot in executor.map(lambda _: index.get(), range(8)))
    assert len(reads) == 1
    CatalogStore(store.path).upsert_movie(movie.model_copy(update={'title': 'New title'}), fetched_at=STAMP)
    second = index.get()
    assert second is not first and second.movies[0].title == 'New title'
    assert len(reads) == 2


def test_write_during_read_does_not_poison_revision_cache(tmp_path, monkeypatch):
    store = CatalogStore(tmp_path / 'movies.db')
    movie = load_catalog()[0].model_copy(update={'source': 'tmdb'})
    store.import_movies([movie], fetched_at=STAMP)
    original, calls = store.identity_movies, []
    def interrupted():
        result = original()
        if not calls:
            store.upsert_movie(movie.model_copy(update={'title': 'Updated during read'}), fetched_at=STAMP)
        calls.append(1)
        return result
    monkeypatch.setattr(store, 'identity_movies', interrupted)
    index = SavedCatalogIndex(store)
    assert index.get().movies[0].title == 'Updated during read'
    assert len(calls) == 2
    assert index.get().movies[0].title == 'Updated during read'
    assert len(calls) == 2


def test_suggestion_labels_are_reused_and_invalidated_by_remember():
    prepared = PreparedCatalog(load_catalog())
    index = prepared.suggestions
    index.suggest('Interstell')
    compiled = index._compiled
    assert index.suggest('Intersteler').items[0].label == 'Interstellar'
    assert index._compiled is compiled
    index.remember(load_catalog()[0].model_copy(update={'title': 'Newly Discovered'}))
    assert index.suggest('Newly Discovere').items[0].label == 'Newly Discovered'
    assert index._compiled is not compiled
