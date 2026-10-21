import asyncio
from datetime import datetime, timezone, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from movie_companion.movie_extras import WatchOptions, WatchRegions, RelatedMovies, watch_options, watch_regions, related_movies
from movie_companion.movie_extras_store import MovieExtrasStore, load_extra
from movie_companion.tmdb_client import TmdbClient, ProviderError
from movie_companion.main import app, get_extras_store, get_detail_provider

NOW=datetime(2026,10,11,tzinfo=timezone.utc)


def provider_record(**changes):
    return {'provider_id':8,'provider_name':'Example Stream','logo_path':'/logo.jpg',**changes}


def watch_payload(country='IN',**changes):
    return {'id':27205,'results':{country:{'link':f'https://www.themoviedb.org/movie/27205-inception/watch?locale={country}','flatrate':[provider_record()],'rent':[provider_record(provider_id=9)]}},**changes}


def test_watch_groups_dedupe_and_keep_country_isolation():
    payload=watch_payload()
    payload['results']['IN']['flatrate'].append(provider_record())
    result=watch_options(payload,27205,'IN')
    assert [group.kind for group in result.groups]==['subscription','rent']
    assert len(result.groups[0].providers)==1
    assert result.groups[0].providers[0].logo_url=='https://image.tmdb.org/t/p/w92/logo.jpg'
    assert watch_options(payload,27205,'US').status=='unavailable'


@pytest.mark.parametrize('link',['https://evil.example/movie/27205/watch?locale=IN','https://www.themoviedb.org.evil.example/movie/27205/watch?locale=IN','https://www.themoviedb.org/movie/999/watch?locale=IN','https://www.themoviedb.org/movie/27205/watch?locale=US','https://[invalid'])
def test_untrusted_watch_links_are_omitted_without_losing_providers(link):
    payload=watch_payload();payload['results']['IN']['link']=link
    result=watch_options(payload,27205,'IN')
    assert result.watch_url is None and result.status=='available'


def test_untrusted_logos_and_invalid_identity_or_bounds():
    payload=watch_payload();payload['results']['IN']['flatrate'][0]['logo_path']='https://evil.example/a.jpg'
    assert watch_options(payload,27205,'IN').groups[0].providers[0].logo_url is None
    for bad in [watch_payload(id=999),watch_payload(id=True),{'id':27205,'results':[]}, {'id':27205,'results':{'IN':{'buy':[provider_record()]*101}}}]:
        with pytest.raises(ValueError):watch_options(bad,27205,'IN')


def test_recommendations_are_lightweight_unique_bounded_and_include_adult_films():
    records=[{'id':27205,'title':'Source'},{'id':True,'title':'Invalid'}, {'id':3,'title':'Adult film','adult':True,'release_date':'2001-01-01','poster_path':'https://evil.example/a.jpg'}]
    records += [{'id':i,'title':f'Film {i}','poster_path':'/poster.jpg','release_date':'bad'} for i in range(3,20)]
    result=related_movies({'results':records},27205)
    assert len(result.items)==6 and len({item.id for item in result.items})==6
    assert result.items[0].adult is True and result.items[0].poster_url is None
    assert result.items[1].year is None
    with pytest.raises(ValueError):related_movies({'results':records*10},27205)


def test_region_list_validates_dedupes_and_sorts():
    result=watch_regions({'results':[{'iso_3166_1':'US','english_name':'United States'},{'iso_3166_1':'IN','english_name':'India'},{'iso_3166_1':'IN','english_name':'India'}]})
    assert [r.code for r in result.items]==['IN','US']
    with pytest.raises(ValueError):watch_regions({'results':[{'iso_3166_1':'invalid','english_name':'Bad'}]})


def load_watch(store,provider,country='IN',now=NOW):
    return asyncio.run(load_extra(f'watch:27205:{country}',WatchOptions,store=store,provider=provider,
        fetch=lambda p:p.watch_options(27205,country),ttl=timedelta(hours=6),stale_for=timedelta(days=3),now=now,
        matches=lambda r:r.movie_id==27205 and r.country==country))


class Provider:
    calls=0
    failing=False
    async def watch_options(self,id,country):
        self.calls+=1
        if self.failing:raise ProviderError(503,'Unavailable')
        return watch_options(watch_payload(country),id,country)


def test_saved_cache_survives_restart_separates_countries_and_expires(tmp_path):
    path=tmp_path/'extras.db';store=MovieExtrasStore(path);provider=Provider()
    first=load_watch(store,provider)
    assert load_watch(MovieExtrasStore(path),provider)==first and provider.calls==1
    assert load_watch(store,provider,'US').country=='US' and provider.calls==2
    assert load_watch(store,provider,now=NOW+timedelta(hours=6)).checked_at==NOW+timedelta(hours=6)
    assert provider.calls==3


def test_stale_fallback_is_labelled_bounded_and_never_used_for_another_country(tmp_path):
    store=MovieExtrasStore(tmp_path/'extras.db');provider=Provider()
    load_watch(store,provider);provider.failing=True
    assert load_watch(store,provider,now=NOW+timedelta(hours=7)).stale
    with pytest.raises(ProviderError):load_watch(store,provider,'US',now=NOW+timedelta(hours=7))
    with pytest.raises(ProviderError):load_watch(store,provider,now=NOW+timedelta(days=4))
    assert load_watch(store,None,now=NOW+timedelta(hours=7)).stale


def test_negative_results_are_saved_and_reused(tmp_path):
    store=MovieExtrasStore(tmp_path/'extras.db')
    class Empty(Provider):
        async def watch_options(self,id,country):
            self.calls+=1
            return WatchOptions(movie_id=id,country=country,status='unavailable')
    provider=Empty()
    assert load_watch(store,provider).status=='unavailable'
    assert load_watch(store,provider).status=='unavailable' and provider.calls==1


def test_saved_identity_mismatch_and_corruption_fail_safely(tmp_path):
    store=MovieExtrasStore(tmp_path/'extras.db')
    store.put('watch:27205:IN',WatchOptions(movie_id=99,country='IN',checked_at=NOW))
    with pytest.raises(ProviderError):load_watch(store,Provider())


def test_provider_endpoints_do_not_hydrate_related_movies():
    paths=[]
    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/watch/providers'):return httpx.Response(200,json=watch_payload())
        if request.url.path.endswith('/regions'):return httpx.Response(200,json={'results':[]})
        assert request.url.params['page']=='1'
        return httpx.Response(200,json={'results':[{'id':9,'title':'Related'}]})
    async def scenario():
        async with httpx.AsyncClient(base_url='https://api.themoviedb.org/3',transport=httpx.MockTransport(handler)) as http:
            client=TmdbClient(http)
            assert (await client.watch_options(27205,'IN')).status=='available'
            assert (await client.related_movies(27205)).items[0].id==9
            assert (await client.watch_regions()).items==[]
    asyncio.run(scenario())
    assert len(paths)==3


def test_routes_validate_country_and_independently_serve_cached_extras(tmp_path):
    store=MovieExtrasStore(tmp_path/'extras.db');provider=Provider()
    app.dependency_overrides[get_extras_store]=lambda:store
    app.dependency_overrides[get_detail_provider]=lambda:provider
    try:
        with TestClient(app) as client:
            assert client.get('/api/movies/27205/watch?country=india').status_code==422
            response=client.get('/api/movies/27205/watch?country=IN')
            assert response.status_code==200 and response.json()['country']=='IN'
            provider.failing=True
            assert client.get('/api/movies/27205/watch?country=IN').status_code==200
            assert client.get('/api/movies/27205/watch?country=US').status_code==503
    finally:
        app.dependency_overrides.pop(get_extras_store,None)
        app.dependency_overrides.pop(get_detail_provider,None)


def test_cache_capacity_and_future_dates(tmp_path):
    import sqlite3
    store=MovieExtrasStore(tmp_path/'extras.db')
    old=WatchOptions(movie_id=1,country='IN',checked_at=NOW-timedelta(days=1))
    with sqlite3.connect(store.path) as db:
        db.executemany('INSERT INTO extras VALUES (?,?,?)',[(f'old:{i}',old.model_dump_json(),old.checked_at.isoformat()) for i in range(2000)])
    store.put('watch:27205:IN',WatchOptions(movie_id=27205,country='IN',checked_at=NOW))
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM extras').fetchone()[0]==2000
    assert store.get('watch:27205:IN') is not None
    with pytest.raises(ProviderError):load_watch(store,None,now=NOW-timedelta(hours=1))


def test_whole_fetch_timeout_uses_labelled_fallback(tmp_path,monkeypatch):
    store=MovieExtrasStore(tmp_path/'extras.db');provider=Provider()
    load_watch(store,provider)
    real_timeout=asyncio.timeout
    monkeypatch.setattr(asyncio,'timeout',lambda seconds:real_timeout(0.01))
    class Slow(Provider):
        async def watch_options(self,id,country):
            await asyncio.sleep(1)
    assert load_watch(store,Slow(),now=NOW+timedelta(hours=7)).stale
