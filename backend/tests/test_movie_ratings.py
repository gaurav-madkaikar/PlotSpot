import asyncio
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from movie_companion.catalog import load_catalog
from movie_companion.schemas import Movie,MovieMetadata
from movie_companion.catalog_search import CatalogQuery,search_catalog
from movie_companion.movie_ratings import movie_rating
from movie_companion.main import app
from test_unified_discovery import setup,save,film
from movie_companion.name_discovery import MovieNameCandidate
from movie_companion.movie_preview import map_movie_preview


def rated(mid,title,score=None,votes=None,**changes):
    return load_catalog()[0].model_copy(update={'id':mid,'title':title,'cast':['Actor Example'],'director':'Director Example',
        'overview':'A lighthouse mystery.','genres':['Drama'],'language':'English','runtime_minutes':100,
        'detail_metadata':None,'vote_average':score,'vote_count':votes,**changes})


def test_ratings_order_entire_pool_before_pagination_with_stable_vote_ties():
    movies=[rated(1,'A',7,500),rated(2,'B',9,10),rated(3,'C',9,100),rated(4,'D',10,0),rated(5,'E')]
    pages=[search_catalog(movies,CatalogQuery(page=p,page_size=2)) for p in range(1,4)]
    assert [m.id for page in pages for m in page.items]==[3,2,1,4,5]
    assert all(p.total==5 and p.total_pages==3 for p in pages)


def test_filter_composition_excludes_unknowns_and_preserves_exact_identity():
    movies=[rated(1,'Lighthouse',6,10),rated(2,'Lighthouse Returns',9,100),rated(3,'Other',10,10),rated(4,'Missing',9,0)]
    exact=search_catalog(movies,CatalogQuery(query='Lighthouse'))
    assert exact.items[0].id==1
    filtered=search_catalog(movies,CatalogQuery(query='lighthouse',min_rating=8,genre='Drama',language='English',max_runtime=110))
    # Titles retain relevance priority over incidental descriptions.
    assert [m.id for m in filtered.items]==[2,3]
    assert search_catalog(movies,CatalogQuery(min_rating=8,max_runtime=90)).total==0
    assert search_catalog(movies,CatalogQuery(min_rating=0)).total==3
    assert [m.id for m in search_catalog(movies,CatalogQuery(query='Actor Example')).items]==[2,3,1,4]
    assert [m.id for m in search_catalog(movies,CatalogQuery(query='Actor Example',sort_by='rating')).items]==[3,2,1,4]


def test_full_metadata_is_authoritative_and_old_payloads_remain_valid():
    movie=rated(1,'Full',9,100,detail_metadata=MovieMetadata(vote_average=7.5,vote_count=20))
    assert movie_rating(movie)==(7.5,20)
    movie.detail_metadata=MovieMetadata(vote_average=None,vote_count=0)
    assert movie_rating(movie)==(None,0)
    old=load_catalog()[0].model_dump(exclude={'vote_average','vote_count'})
    assert Movie.model_validate(old).vote_average is None
    assert movie_rating(rated(1,'Zero',0,2))==(0,2)


@pytest.mark.parametrize('value',['bad','NaN','Infinity','-0.1','10.1'])
def test_rating_query_bounds(value):
    for endpoint in ('/api/search/catalog','/api/search/local'):
        assert TestClient(app).get(endpoint,params={'min_rating':value}).status_code==422


@pytest.mark.parametrize('changes',[{'vote_average':11},{'vote_average':float('nan')},{'vote_average':True},{'vote_count':-1},{'vote_count':True}])
def test_compact_rating_boundary_rejects_malformed_provider_values(changes):
    with pytest.raises(ValidationError):MovieNameCandidate(id=1,title='Bad score',**changes)


def test_candidate_preview_keeps_scores_without_full_presentation():
    candidate=MovieNameCandidate(id=123,title='Preview',vote_average=8.4,vote_count=210,original_language='en')
    movie=map_movie_preview(candidate.model_dump(),123,[{'iso_639_1':'en','english_name':'English'}])
    assert movie_rating(movie)==(8.4,210) and movie.detail_metadata is None


def test_live_merges_rating_filter_and_snapshot_identity(tmp_path):
    store,provider,service=setup(tmp_path)
    provider.movies={101:film(101,'Lighthouse',vote_average=7, vote_count=100),102:film(102,'Lighthouse Returns',vote_average=9,vote_count=100)}
    save(store,[film(103,'Lighthouse Local',vote_average=8,vote_count=100)])
    async def run():
        first=await service.search(CatalogQuery(query='lighthouse',page_size=1))
        second=await service.search(CatalogQuery(query='lighthouse',min_rating=8,page=2,page_size=1),token=first.search_token)
        assert second.snapshot_reset and second.page==1 and second.total==2
        assert second.items[0].id==102
        third=await service.search(CatalogQuery(query='lighthouse',min_rating=8,page=2,page_size=1),token=second.search_token)
        assert third.items[0].id==103
        assert not third.snapshot_reset
    asyncio.run(run())


def test_legacy_preview_refreshes_missing_votes_from_supplied_name_record(tmp_path):
    store,provider,service=setup(tmp_path)
    save(store,[film(101,'Lighthouse')])
    original=provider.search_movie_names
    async def names(query,*,page):
        result=await original(query,page=page)
        result.items=[m.model_copy(update={'vote_average':8.8,'vote_count':20}) for m in result.items]
        return result
    provider.search_movie_names=names
    provider.movies[101]=film(101,'Lighthouse',vote_average=8.8,vote_count=20)
    result=asyncio.run(service.search(CatalogQuery(query='lighthouse',min_rating=8)))
    assert 101 in [m.id for m in result.items]
    assert movie_rating(store.get_movie(101))==(8.8,20)


def test_related_preview_preserves_compact_rating_fields():
    from movie_companion.movie_extras import related_movies
    result=related_movies({'results':[{'id':2,'title':'Related','vote_average':8.7,'vote_count':50}]},1)
    assert result.items[0].vote_average==8.7 and result.items[0].vote_count==50


def test_selected_actor_credit_pool_obeys_rating_filter(tmp_path):
    from movie_companion.name_discovery import PersonNameCandidate
    store,provider,service=setup(tmp_path)
    provider.people=[PersonNameCandidate(id=77,name='Actor Example',known_for_department='Acting')]
    provider.movies={101:film(101,'Low score',vote_average=7,vote_count=10),102:film(102,'High score',vote_average=9,vote_count=50)}
    result=asyncio.run(service.search(CatalogQuery(query='Actor Example',min_rating=8),person_id=77,role='actor'))
    assert [m.id for m in result.items]==[102] and result.selected_person.id==77
