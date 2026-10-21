import asyncio

import pytest
from fastapi.testclient import TestClient

from movie_companion.catalog import load_catalog
from movie_companion.catalog_search import CatalogQuery, search_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.main import app, get_provider, get_catalog_store
from movie_companion.name_discovery import MovieNameCandidate, PersonNameCandidate, NamePage
from movie_companion.name_search import NameSearchRequest, search_names
from movie_companion.semantic_search import SemanticSearch
from movie_companion.tmdb_client import ProviderError


class Provider:
    def __init__(self):
        self.calls = []
        self.failures = {}
        self.cast = [{'id': mid} for mid in range(101, 124)]
        self.crew = [{'id': 102, 'job': 'Director'}, {'id': 102, 'job': 'Director'},
                     {'id': 101, 'job': 'Producer'}, {'id': 103, 'job': 'Director of Photography'}]

    async def search_movie_names(self, query, *, page):
        if 'titles' in self.failures:
            raise self.failures['titles']
        return NamePage[MovieNameCandidate](items=[MovieNameCandidate(id=i, title=f'Film {i}') for i in [101, 102]], page=page, total_pages=1)

    async def search_person_names(self, query, *, page):
        if 'people' in self.failures:
            raise self.failures['people']
        return NamePage[PersonNameCandidate](items=[PersonNameCandidate(id=i, name='Alex Lee', known_for_department=d) for i, d in [(1, 'Acting'), (2, 'Directing')]], page=page, total_pages=1)

    async def person(self, person_id):
        return PersonNameCandidate(id=person_id, name='Alex Lee')

    async def person_movie_credits(self, person_id):
        return {'cast': self.cast, 'crew': self.crew}

    async def movie(self, movie_id, *, enrich):
        self.calls.append(movie_id)
        assert enrich
        if movie_id in self.failures:
            raise self.failures[movie_id]
        return load_catalog()[0].model_copy(update={'id': movie_id, 'title': f'Film {movie_id}', 'source': 'tmdb', 'adult': True, 'director': 'Alex Lee'})


def run(provider, store, **kwargs):
    return asyncio.run(search_names(provider, store, NameSearchRequest(query='Alex Lee', **kwargs)))


def test_ambiguous_people_are_choices_and_movies_survive_restart(tmp_path):
    path = tmp_path / 'movies.db'
    provider = Provider()
    first = run(provider, CatalogStore(path))
    assert [p.id for p in first.people] == [1, 2]
    assert first.selected_person is None
    assert all(m.adult is True for m in first.items)
    assert CatalogStore(path).get_movie(101).adult is True
    provider.failures[101] = ProviderError(503, 'Unavailable')
    assert run(provider, CatalogStore(path)).items == first.items
    assert provider.calls.count(101) == 1


def test_actor_pages_are_bounded_and_director_roles_are_exact(tmp_path):
    store, provider = CatalogStore(tmp_path / 'movies.db'), Provider()
    first = run(provider, store, person_id=2, role='actor')
    assert len(first.items) == 20 and first.has_more
    second = run(provider, store, person_id=2, role='actor', page=2)
    assert [m.id for m in second.items] == [121, 122, 123] and not second.has_more
    directed = run(provider, store, person_id=2, role='director')
    assert [m.id for m in directed.items] == [102]
    assert directed.selected_person.id == 2


@pytest.mark.parametrize('status', [404, 502, 503, 504])
def test_partial_hydration_keeps_good_results(tmp_path, status):
    provider = Provider()
    provider.failures[102] = ProviderError(status, 'Unavailable')
    store = CatalogStore(tmp_path / 'movies.db')
    result = run(provider, store)
    assert [m.id for m in result.items] == [101] and result.partial
    assert store.get_movie(102) is None


def test_stale_fallback_does_not_get_a_new_freshness_timestamp(tmp_path):
    provider, store = Provider(), CatalogStore(tmp_path / 'movies.db')
    stale = asyncio.run(provider.movie(101, enrich=True))
    store.upsert_movie(stale, fetched_at='2000-01-01T00:00:00+00:00')
    provider.failures[101] = ProviderError(503, 'Unavailable')
    result = run(provider, store)
    assert result.partial and len(result.items) == 2
    assert not store.metadata_is_fresh(101)
    assert store.metadata_is_fresh(102)


@pytest.mark.parametrize('filters', [{'genre': 'Comedy'}, {'language': 'Korean'}, {'max_runtime': 120}])
def test_filters_apply_after_hydration_without_claiming_global_totals(tmp_path, filters):
    store = CatalogStore(tmp_path / 'movies.db')
    result = run(Provider(), store, **filters)
    assert result.items == []
    assert store.get_movie(101) is not None
    assert 'total' not in result.model_dump()


def test_one_discovery_branch_can_fail_without_losing_other_branch(tmp_path):
    provider = Provider()
    provider.failures['titles'] = ProviderError(503, 'Unavailable')
    result = run(provider, CatalogStore(tmp_path / 'movies.db'))
    assert len(result.people) == 2 and not result.items and result.partial


def test_total_provider_failure_is_retryable(tmp_path):
    provider = Provider()
    provider.failures = {'titles': ProviderError(503, 'Unavailable'), 'people': ProviderError(503, 'Unavailable')}
    with pytest.raises(ProviderError):
        run(provider, CatalogStore(tmp_path / 'movies.db'))


def test_saved_external_metadata_is_immediately_keyword_searchable(tmp_path):
    store = CatalogStore(tmp_path / 'movies.db')
    run(Provider(), store)
    service = SemanticSearch(None)
    named = search_catalog([*load_catalog(), *store.identity_movies()], CatalogQuery(query='Film 101'), demo=True)
    assert [m.id for m in named.items] == [101]
    director = search_catalog([*load_catalog(), *store.identity_movies()], CatalogQuery(query='movies directed by Alex Lee'), demo=True)
    assert [m.id for m in director.items] == [101, 102]
    story = search_catalog([*load_catalog(), *store.identity_movies()], CatalogQuery(query='science fiction'), demo=True)
    assert {101, 102} <= {m.id for m in story.items}


def test_route_validation_and_provider_boundary(tmp_path):
    app.dependency_overrides[get_provider] = lambda: Provider()
    app.dependency_overrides[get_catalog_store] = lambda: CatalogStore(tmp_path / 'movies.db')
    try:
        with TestClient(app) as client:
            for url in ['/api/search/names?q=Alex&page=101', '/api/search/names?q=Alex&person_id=0', '/api/search/names?q=Alex&role=producer']:
                assert client.get(url).status_code == 422
            response = client.get('/api/search/names?q=Alex&person_id=2&role=director')
            assert response.status_code == 200
            assert [m['id'] for m in response.json()['items']] == [102]
    finally:
        app.dependency_overrides.clear()


def test_adult_classification_changes_fingerprint_but_unknown_is_backward_compatible():
    import hashlib
    import json
    from movie_companion.semantic_catalog import MODEL, fingerprint
    original = load_catalog()[0]
    legacy = original.model_dump(mode="json", exclude={"adult", "detail_metadata"})
    old_hash = hashlib.sha256((MODEL + "\nmetadata-v2\n" + json.dumps([legacy], sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
    assert fingerprint([original]) == old_hash
    assert fingerprint([original.model_copy(update={"adult": True})]) != old_hash


def test_local_explicit_role_does_not_mix_actor_and_director():
    from movie_companion.catalog_search import identity_matches
    base = load_catalog()[0]
    acting = base.model_copy(update={"id": 101, "title": "First", "cast": ["Alex Lee"], "director": "Other Person"})
    directing = base.model_copy(update={"id": 102, "title": "Second", "cast": ["Other Person"], "director": "Alex Lee"})
    assert [m.id for m in identity_matches([acting, directing], 'movies directed by Alex Lee')] == [102]
    assert [m.id for m in identity_matches([acting, directing], 'movies starring Alex Lee')] == [101]
    assert {m.id for m in identity_matches([acting, directing], 'Alex Lee')} == {101, 102}
