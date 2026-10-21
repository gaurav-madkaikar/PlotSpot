import asyncio
from datetime import datetime, timezone

import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_search import CatalogQuery
from movie_companion.catalog_store import CatalogStore
from movie_companion.name_discovery import MovieNameCandidate, PersonNameCandidate, NamePage
from movie_companion.tmdb_client import ProviderError
from movie_companion.unified_discovery import UnifiedDiscovery


def film(mid, title='Lighthouse', **fields):
    return load_catalog()[0].model_copy(update={'id': mid, 'title': title, 'source': 'tmdb',
        'cast': [], 'director': 'Other', 'overview': 'A courier explores the coast.',
        'runtime_minutes': 100, 'language': 'English', 'genres': ['Drama'], **fields})


class Provider:
    def __init__(self):
        self.movies = {101: film(101, adult=True), 102: film(102, 'Lighthouse Returns')}
        self.title_ids = [101, 102]
        self.people = []
        self.credits = {'cast': [{'id': 101}, {'id': 102}], 'crew': [
            {'id': 102, 'job': 'Director'}, {'id': 101, 'job': 'Producer'}]}
        self.calls, self.failure, self.delayed, self.pages = [], set(), set(), 1

    async def search_movie_names(self, query, *, page):
        self.calls.append(('title', query, page))
        if 'title' in self.failure: raise ProviderError(503, 'Unavailable')
        return NamePage[MovieNameCandidate](items=[MovieNameCandidate(id=mid, title=self.movies[mid].title)
            for mid in self.title_ids], page=page, total_pages=self.pages)

    async def search_person_names(self, query, *, page):
        self.calls.append(('person', query, page))
        if 'person' in self.failure: raise ProviderError(503, 'Unavailable')
        return NamePage[PersonNameCandidate](items=self.people, page=page, total_pages=1)

    async def person(self, mid):
        return next(p for p in self.people if p.id == mid)

    async def person_movie_credits(self, mid):
        self.calls.append(('credits', mid))
        return self.credits

    async def movie(self, mid, *, enrich):
        self.calls.append(('movie', mid))
        assert enrich
        if mid in self.delayed: await asyncio.sleep(.15)
        if mid in self.failure: raise ProviderError(503, 'Unavailable')
        return self.movies[mid]

    async def movie_preview(self, mid, *, candidate=None, require_runtime=False):
        return await self.movie(mid, enrich=True)


def setup(tmp_path, **kwargs):
    store = CatalogStore(tmp_path/'catalog.db')
    provider = Provider()
    return store, provider, UnifiedDiscovery(provider, store, **kwargs)


def save(store, movies, timestamp=None):
    store.import_movies(movies, fetched_at=timestamp or datetime.now(timezone.utc).isoformat())


def test_merges_external_with_local_matches_deduplicates_and_preserves_adult(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(101, adult=True), film(103, 'Lighthouse Local')])
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse')))
    assert {m.id for m in result.items} == {101, 102, 103}
    assert result.total == 3 and not result.partial
    assert CatalogStore(store.path).get_movie(101).adult is True
    assert store.get_movie(102).title == 'Lighthouse Returns'
    assert ('title', 'lighthouse', 1) in provider.calls and ('movie', 101) not in provider.calls


def test_title_completion_keeps_rank_when_live_matches_are_merged(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103, 'Interstellar')])
    provider.movies = {101: film(101, 'Angry Planet', alternative_titles=['Interstellar Combat']),
                       102: film(102, 'Container Interstellar')}
    result = asyncio.run(service.search(CatalogQuery(query='Interstell', page_size=1)))
    assert result.items[0].id == 103 and result.total == 3


def test_local_preview_does_not_wait_for_or_call_provider(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103, 'Interstellar'), film(104, 'Interstellar Wars')])
    result = asyncio.run(service.local_preview(CatalogQuery(query='Interstell')))
    assert result.items[0].id == 103 and result.total == 2
    assert result.search_token is None and result.total_pages == 0 and provider.calls == []


def test_local_preview_preserves_filters_and_withholds_person_identity_guesses(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103, 'Interstellar', cast=['Alex Lee'])])
    async def scenario():
        assert (await service.local_preview(CatalogQuery(query='Interstell', genre='Comedy'))).items == []
        assert (await service.local_preview(CatalogQuery(query='Alex Lee'))).items == []
        assert (await service.local_preview(CatalogQuery(query='Interstell'), person_id=1)).items == []
        assert (await service.local_preview(CatalogQuery(query='directed by Other'))).items == []
        assert (await service.local_preview(CatalogQuery(query='coast'))).items[0].id == 103
    asyncio.run(scenario())
    assert provider.calls == []


def test_local_preview_api_has_no_provider_work_or_pagination_token(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from movie_companion.main import app
    from movie_companion.settings import get_settings
    store, provider, service = setup(tmp_path)
    save(store, [film(103, 'Interstellar')])
    monkeypatch.setattr(get_settings(), 'data_source', 'tmdb')
    monkeypatch.setattr(app.state, 'catalog_store', store, raising=False)
    monkeypatch.setattr(app.state, 'unified_discovery', service, raising=False)
    client = TestClient(app)
    response = client.get('/api/search/local', params={'q':'Interstell'})
    assert response.status_code == 200 and response.json()['items'][0]['id'] == 103
    assert response.json()['search_token'] is None and provider.calls == []
    assert client.get('/api/search/local', params={'q':'Interstell', 'page':2}).status_code == 400
    assert client.get('/api/search/local', params={'q':'x'*301}).status_code == 422


def test_missing_runtime_in_fresh_preview_is_loaded_before_filtering(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(101, runtime_minutes=None)])
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse', max_runtime=120)))
    assert 101 in [m.id for m in result.items]
    assert ('movie', 101) in provider.calls


@pytest.mark.parametrize('role,expected', [('actor', {101, 102}), ('director', {102})])
def test_person_credits_work_without_top_cast_and_director_job_is_exact(tmp_path, role, expected):
    store, provider, service = setup(tmp_path)
    provider.title_ids = []
    provider.people = [PersonNameCandidate(id=1, name='Alex Lee', known_for_department='Directing')]
    save(store, [film(101), film(102)])
    result = asyncio.run(service.search(CatalogQuery(query='Alex Lee'), role=role))
    assert {m.id for m in result.items} == expected
    assert result.selected_person.id == 1 and result.person_role == role and result.people == []


def test_ambiguous_names_require_choice_and_selected_id_excludes_other_same_name(tmp_path):
    store, provider, service = setup(tmp_path)
    provider.people = [PersonNameCandidate(id=i, name='Alex Lee', known_for_department=dept)
                       for i, dept in [(1, 'Acting'), (2, 'Directing')]]
    save(store, [film(103, 'Unrelated', cast=['Alex Lee'])])
    result = asyncio.run(service.search(CatalogQuery(query='Alex Lee')))
    assert result.selected_person is None and len(result.people) == 2
    assert not any(call[0] == 'credits' for call in provider.calls)
    selected = asyncio.run(service.search(CatalogQuery(query='Alex Lee'), person_id=2, role='director'))
    assert selected.selected_person.id == 2 and [m.id for m in selected.items] == [102]


@pytest.mark.parametrize('filters', [{'genre': 'Comedy'}, {'language': 'Korean'}, {'max_runtime': 80}])
def test_filters_apply_to_both_sources(tmp_path, filters):
    store, _, service = setup(tmp_path)
    save(store, [film(103)])
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse', **filters)))
    assert result.items == [] and result.total == 0
    assert store.get_movie(101) is not None


def test_snapshot_freezes_pages_after_catalog_growth_and_resets_mismatched_query(tmp_path):
    store, provider, service = setup(tmp_path)
    async def scenario():
        first = await service.search(CatalogQuery(query='Lighthouse', page_size=1))
        calls = list(provider.calls)
        save(store, [film(999, 'Lighthouse AAA')])
        second = await service.search(CatalogQuery(query='Lighthouse', page=2, page_size=1), token=first.search_token)
        assert [m.id for m in second.items] == [102]
        assert second.total == first.total == 2 and provider.calls == calls
        all_items = await service.search(CatalogQuery(query='Lighthouse', page_size=20), token=first.search_token)
        assert [m.id for m in all_items.items] == [101, 102]
        reset = await service.search(CatalogQuery(query='coast', page=2), token=first.search_token)
        assert reset.snapshot_reset and reset.page == 1 and reset.search_token != first.search_token
    asyncio.run(scenario())


def test_expired_token_restarts_first_page(tmp_path):
    _, _, service = setup(tmp_path, ttl=0)
    async def scenario():
        first = await service.search(CatalogQuery(query='Lighthouse', page_size=1))
        second = await service.search(CatalogQuery(query='Lighthouse', page=2, page_size=1), token=first.search_token)
        assert second.page == 1 and second.snapshot_reset and second.search_token != first.search_token
    asyncio.run(scenario())


def test_failure_keeps_local_and_retry_recovers(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103)])
    provider.failure = {'title', 'person'}
    async def scenario():
        first = await service.search(CatalogQuery(query='Lighthouse'))
        assert first.partial and [m.id for m in first.items] == [103]
        provider.failure.clear()
        second = await service.search(CatalogQuery(query='Lighthouse'), token=first.search_token)
        assert not second.partial and second.total == 3
    asyncio.run(scenario())


def test_timeout_keeps_completed_discovery_and_joins_cancelled_work(tmp_path):
    store, provider, service = setup(tmp_path, deadline=.04)
    provider.delayed = {102}
    async def scenario():
        result = await service.search(CatalogQuery(query='Lighthouse'))
        assert result.partial and [m.id for m in result.items] == [101]
        assert store.get_movie(101) is not None and store.get_movie(102) is None
        await asyncio.sleep(.2)
        assert store.get_movie(102) is None
    asyncio.run(scenario())


def test_stale_fallback_does_not_refresh_failed_record(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(101)], '2000-01-01T00:00:00+00:00')
    provider.failure = {101}
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse')))
    assert result.partial and result.total == 2 and not store.metadata_is_fresh(101)


def test_concurrent_requests_share_work_and_survive_one_cancelled_client(tmp_path):
    _, provider, service = setup(tmp_path)
    provider.delayed = {101, 102}
    async def scenario():
        query = CatalogQuery(query='Lighthouse')
        first, second = asyncio.create_task(service.search(query)), asyncio.create_task(service.search(query))
        await asyncio.sleep(.04)
        first.cancel()
        with pytest.raises(asyncio.CancelledError): await first
        result = await second
        assert result.total == 2 and provider.calls.count(('movie', 101)) == 1
        assert provider.calls.count(('title', 'lighthouse', 1)) == 1 and not service.pending
    asyncio.run(scenario())


def test_work_cache_and_saved_credit_membership_are_bounded(tmp_path):
    store, provider, service = setup(tmp_path, movie_limit=1, capacity=1)
    provider.people = [PersonNameCandidate(id=1, name='Alex Lee')]
    save(store, [film(102)])
    async def scenario():
        first = await service.search(CatalogQuery(query='Alex Lee'))
        assert first.limited and first.total == 2
        assert ('movie', 101) in provider.calls and ('movie', 102) not in provider.calls
        await service.search(CatalogQuery(query='Lighthouse'))
        assert len(service.snapshots) == 1 and first.search_token not in service.snapshots
    asyncio.run(scenario())


def test_second_title_page_uses_original_query_despite_local_correction(tmp_path):
    store, provider, service = setup(tmp_path)
    provider.pages = 3
    save(store, [film(103, 'Lighthouses')])
    result = asyncio.run(service.search(CatalogQuery(query='Lighthous')))
    assert ('title', 'lighthous', 2) in provider.calls and result.limited


def test_wrong_hydrated_identity_is_withheld_not_persisted(tmp_path):
    store, provider, service = setup(tmp_path)
    provider.movies[101] = film(999)
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse')))
    assert result.partial and [m.id for m in result.items] == [102]
    assert store.get_movie(999) is None and store.get_movie(101) is None


def test_one_failed_branch_preserves_other_branch(tmp_path):
    _, provider, service = setup(tmp_path)
    provider.failure = {'person'}
    result = asyncio.run(service.search(CatalogQuery(query='Lighthouse')))
    assert result.partial and {m.id for m in result.items} == {101, 102}


def test_saturated_external_admission_returns_local_and_shutdown_joins_work(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103)])
    provider.delayed = {101, 102}
    async def scenario():
        first = asyncio.create_task(service.search(CatalogQuery(query='first')))
        second = asyncio.create_task(service.search(CatalogQuery(query='second')))
        for _ in range(100):
            if service.slots.locked(): break
            await asyncio.sleep(.001)
        third = await service.search(CatalogQuery(query='Lighthouse'))
        assert third.partial and [m.id for m in third.items] == [103]
        assert ('title', 'lighthouse', 1) not in provider.calls
        await service.close()
        outcomes = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(r, asyncio.CancelledError) for r in outcomes)
        assert not service.pending
    asyncio.run(scenario())


def test_tmdb_route_uses_service_and_validates_token_and_roles(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from movie_companion.main import app
    from movie_companion.settings import get_settings
    store, _, service = setup(tmp_path)
    monkeypatch.setattr(get_settings(), 'data_source', 'tmdb')
    monkeypatch.setattr(app.state, 'catalog_store', store, raising=False)
    monkeypatch.setattr(app.state, 'unified_discovery', service, raising=False)
    client = TestClient(app)
    response = client.get('/api/search/catalog', params={'q': 'Lighthouse', 'page_size': 1})
    assert response.status_code == 200
    first = response.json()
    assert first['data_source'] == 'tmdb' and first['total'] == 2
    second = client.get('/api/search/catalog', params={'q': 'Lighthouse', 'page_size': 1, 'page': 2,
        'search_token': first['search_token']}).json()
    assert second['items'][0]['id'] != first['items'][0]['id']
    for params in [{'search_token': 'invalid'}, {'person_id': 0}, {'role': 'producer'}]:
        assert client.get('/api/search/catalog', params={'q': 'Alex', **params}).status_code == 422


def test_valid_external_exact_title_overrides_local_typo_guess(tmp_path):
    store, provider, service = setup(tmp_path)
    save(store, [film(103, 'Lighthouses')])
    provider.title_ids = [101]
    provider.movies[101] = film(101, 'Lighthous')
    result = asyncio.run(service.search(CatalogQuery(query='Lighthous')))
    assert result.matched_query is None and result.items[0].id == 101
