import asyncio
import math
import pytest
from fastapi.testclient import TestClient
from movie_companion.catalog_search import CatalogQuery, search_catalog
from movie_companion.main import app
from movie_companion.movie_ratings import trusted_rating, REFERENCE_SCORE
from movie_companion.schemas import MovieMetadata
from test_movie_ratings import rated
from test_unified_discovery import setup, save, film


def test_two_vote_perfect_score_does_not_dominate_and_raw_score_is_preserved():
    tiny=rated(1,'Two votes',10,2);established=rated(2,'Established',8.5,10000)
    before=[m.model_dump() for m in [tiny,established]]
    assert [m.id for m in search_catalog([tiny,established],CatalogQuery()).items]==[2,1]
    assert [m.id for m in search_catalog([tiny,established],CatalogQuery(sort_by='rating')).items]==[1,2]
    assert [m.model_dump() for m in [tiny,established]]==before
    # A raw minimum remains a raw minimum; we do not silently hide new films.
    assert [m.id for m in search_catalog([tiny,established],CatalogQuery(min_rating=9)).items]==[1]


def test_growing_support_can_raise_a_new_high_score_above_an_established_film():
    new=rated(1,'New',9,10);established=rated(2,'Established',8.5,10000)
    initial=trusted_rating(new)
    assert [m.id for m in search_catalog([new,established],CatalogQuery()).items]==[2,1]
    new.vote_count=10000
    assert trusted_rating(new)>initial
    assert [m.id for m in search_catalog([new,established],CatalogQuery()).items]==[1,2]


@pytest.mark.parametrize('score',[0,3,7,8.5,10])
@pytest.mark.parametrize('votes',[1,2,500,100000,10**100])
def test_adjustment_is_finite_bounded_and_keeps_the_reported_scale(score,votes):
    adjusted=trusted_rating(rated(1,'Bounded',score,votes))
    assert math.isfinite(adjusted) and min(REFERENCE_SCORE,score)<=adjusted<=max(REFERENCE_SCORE,score)


def test_unreported_ratings_and_authoritative_full_records():
    assert trusted_rating(rated(1,'Unrated',10,0)) is None
    assert trusted_rating(rated(1,'Missing',None,10)) is None
    full=rated(1,'Full',10,2,detail_metadata=MovieMetadata(vote_average=8.5,vote_count=10000))
    assert trusted_rating(full)==trusted_rating(rated(2,'Compact',8.5,10000))


def test_pages_and_filters_do_not_change_the_reference_or_drop_low_vote_movies():
    movies=[rated(1,'A',10,2),rated(2,'B',8.5,10000),rated(3,'C',9,10000),rated(4,'D'),rated(5,'E',7,1)]
    result=search_catalog(movies,CatalogQuery(page_size=2),paginate=False)
    pages=[search_catalog(movies,CatalogQuery(page=p,page_size=2)) for p in range(1,4)]
    assert [m.id for p in pages for m in p.items]==[m.id for m in result.items]==[3,2,1,5,4]
    assert all(p.total==5 for p in pages)
    assert [m.id for m in search_catalog(movies,CatalogQuery(min_rating=8)).items]==[3,2,1]
    assert [m.id for m in search_catalog(movies,CatalogQuery(sort_by='rating',min_rating=8)).items]==[1,3,2]
    # Exact requested titles retain priority in either mode.
    for mode in ['trusted','rating']:
        assert search_catalog(movies,CatalogQuery(query='A',sort_by=mode)).items[0].id==1


@pytest.mark.parametrize('mode',['popularity','unknown',''])
def test_public_sort_contract_rejects_unknown_modes(mode):
    for path in ['/api/search/catalog','/api/search/local']:
        assert TestClient(app).get(path,params={'sort_by':mode}).status_code==422


def test_public_endpoint_defaults_to_trusted_but_honors_raw_order(monkeypatch):
    movies=[rated(1,'New',10,2),rated(2,'Established',8.5,10000)]
    monkeypatch.setattr('movie_companion.main.load_catalog',lambda:movies)
    client=TestClient(app)
    assert [m['id'] for m in client.get('/api/search/catalog').json()['items']]==[2,1]
    raw=client.get('/api/search/catalog?sort_by=rating').json()['items']
    assert [m['id'] for m in raw]==[1,2] and raw[0]['vote_average']==10


def test_merged_live_pool_and_mode_change_reset_frozen_pagination(tmp_path):
    store,provider,service=setup(tmp_path)
    provider.movies={101:film(101,'New',vote_average=10,vote_count=2),102:film(102,'Established',vote_average=8.5,vote_count=10000)}
    save(store,[film(103,'Local',vote_average=9,vote_count=5000)])
    async def run():
        first=await service.search(CatalogQuery(query='courier',page_size=1))
        assert first.items[0].id==103
        second=await service.search(CatalogQuery(query='courier',sort_by='rating',page=2,page_size=1),token=first.search_token)
        assert second.snapshot_reset and second.page==1 and second.items[0].id==101
        nextpage=await service.search(CatalogQuery(query='courier',sort_by='rating',page=2,page_size=1),token=second.search_token)
        assert not nextpage.snapshot_reset and nextpage.items[0].id==103
    asyncio.run(run())


def test_progressive_local_preview_uses_selected_order_without_provider_calls(tmp_path):
    store,provider,service=setup(tmp_path)
    save(store,[film(101,'New',vote_average=10,vote_count=2),film(102,'Established',vote_average=8.5,vote_count=10000)])
    async def run():
        best=await service.local_preview(CatalogQuery(query='courier'))
        raw=await service.local_preview(CatalogQuery(query='courier',sort_by='rating'))
        assert [m.id for m in best.items]==[102,101] and [m.id for m in raw.items]==[101,102]
        assert provider.calls==[]
    asyncio.run(run())


def test_rating_policy_version_is_part_of_snapshot_identity(tmp_path,monkeypatch):
    store,provider,service=setup(tmp_path)
    async def run():
        first=await service.search(CatalogQuery(query='courier',page_size=1))
        monkeypatch.setattr('movie_companion.unified_discovery.RATING_POLICY','next-test-policy')
        second=await service.search(CatalogQuery(query='courier',page=2,page_size=1),token=first.search_token)
        assert second.snapshot_reset and second.page==1 and second.search_token!=first.search_token
    asyncio.run(run())
