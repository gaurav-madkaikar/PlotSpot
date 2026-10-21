import asyncio
import pytest
from fastapi.testclient import TestClient
from movie_companion.main import app
from movie_companion.accounts import AccountStore
from movie_companion.catalog_search import CatalogQuery, search_catalog
from test_account_routes import setup, register, headers
from test_movie_ratings import rated
from test_unified_discovery import setup as discovery_setup, save, film


def defaults(revision=0, **changes):
    return {'revision':revision, 'allow_spoilers':False, 'include_adult':True, 'track_movie_history':True, **changes}


def test_persistence_isolation_and_conflict(setup):
    first, other = TestClient(app), TestClient(app)
    auth = register(first, 'first_viewer')
    register(other, 'other_viewer')
    initial = first.get('/api/auth/session').json()
    assert initial['user']['preferences'] == defaults()
    response = first.put('/api/me/preferences', headers=auth, json=defaults(allow_spoilers=True,include_adult=False))
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['user']['id'] == initial['user']['id']
    assert response.json()['user']['preferences'] == defaults(1,allow_spoilers=True,include_adult=False)
    assert other.get('/api/auth/session').json()['user']['preferences'] == defaults()
    assert first.get('/api/me/collection').json()['snapshot']['revision'] == 0
    assert first.put('/api/me/preferences',headers=auth,json=defaults()).status_code == 409
    assert first.get('/api/auth/session').json()['user']['preferences']['include_adult'] is False
    reopened = AccountStore(setup.path)
    assert reopened.session(first.cookies.get('frame_session')).user['preferences'] == response.json()['user']['preferences']
    assert first.put('/api/me/preferences',headers=auth,json=defaults(1)).json()['user']['preferences'] == defaults(2)


@pytest.mark.parametrize('changes',[{'include_adult':'false'},{'allow_spoilers':1},{'owner':'forged'}, {'revision':-1},{'revision':True},{'revision':9007199254740992}])
def test_strict_preference_contract(setup,changes):
    client=TestClient(app); auth=register(client,'viewer')
    response=client.put('/api/me/preferences',headers=auth,json={**defaults(),**changes})
    assert response.status_code==422 and response.headers['cache-control']=='no-store'
    assert client.get('/api/auth/session').json()['user']['preferences']==defaults()


def test_guest_and_csrf_cannot_write(setup):
    client=TestClient(app)
    assert client.put('/api/me/preferences',headers=headers(client),json=defaults()).status_code==401
    auth=register(client,'viewer')
    for bad in [{'Origin':setup.origin}, {**auth,'Origin':'https://example.com'}, {**auth,'X-CSRF-Token':'x'*43}]:
        assert client.put('/api/me/preferences',headers=bad,json=defaults(include_adult=False)).status_code==403
    assert client.get('/api/auth/session').json()['user']['preferences']==defaults()


def test_filter_precedes_correction_ranking_and_paging():
    movies=[rated(1,'Adult Example',10,10000,adult=True),rated(2,'Available Film',8,500,adult=False),rated(3,'Unknown Film',7,100)]
    request=CatalogQuery(include_adult=False,page_size=1)
    result=search_catalog(movies,request)
    assert result.total==2 and result.items[0].id==2 and result.total_pages==2
    assert [m.id for m in search_catalog(movies,request.model_copy(update={'page':2})).items]==[3]
    assert search_catalog(movies,CatalogQuery(query='Adult Exampl',include_adult=False)).matched_query is None
    assert search_catalog(movies,CatalogQuery()).items[0].id==1


def test_authenticated_setting_cannot_be_bypassed_by_query(setup,monkeypatch):
    client=TestClient(app);auth=register(client,'viewer')
    monkeypatch.setattr(app.state,'accounts',setup,raising=False)
    movies=[rated(1,'Adult Example',10,10000,adult=True),rated(2,'Available Film',8,500,adult=False)]
    monkeypatch.setattr('movie_companion.main.load_catalog',lambda:movies)
    assert client.put('/api/me/preferences',headers=auth,json=defaults(include_adult=False)).status_code==200
    for path in ['/api/search/catalog','/api/search/local']:
        response=client.get(path,params={'include_adult':'true'})
        assert [m['id'] for m in response.json()['items']]==[2]
        assert response.headers['cache-control']=='no-store' and response.headers['vary']=='Cookie'
    result=client.get('/api/search/suggestions',params={'q':'Adult Exampl','include_adult':'true'})
    assert result.json()['items']==[]
    guest=TestClient(app)
    assert [m['id'] for m in guest.get('/api/search/catalog').json()['items']]==[1,2]


def test_adult_mode_changes_live_snapshot_and_does_not_change_metadata(tmp_path):
    store,provider,service=discovery_setup(tmp_path)
    save(store,[film(101,'Adult courier',adult=True),film(102,'Courier',adult=False)])
    async def run():
        first=await service.search(CatalogQuery(query='courier',page_size=1))
        second=await service.search(CatalogQuery(query='courier',include_adult=False,page=2,page_size=1),token=first.search_token)
        assert second.snapshot_reset and second.page==1
        assert [m.id for m in second.items]==[102] and second.total==1
    asyncio.run(run())
    assert store.get_movie(101).adult is True


@pytest.mark.parametrize('missing',['revision','allow_spoilers','include_adult'])
def test_writes_require_explicit_complete_settings(setup,missing):
    client=TestClient(app);auth=register(client,'viewer')
    body=defaults();body.pop(missing)
    assert client.put('/api/me/preferences',headers=auth,json=body).status_code==422
    assert client.get('/api/auth/session').json()['user']['preferences']==defaults()


def test_known_adult_title_candidates_are_not_hydrated(tmp_path):
    from movie_companion.name_discovery import MovieNameCandidate, NamePage
    store,provider,service=discovery_setup(tmp_path)
    async def titles(query,*,page):
        return NamePage[MovieNameCandidate](items=[MovieNameCandidate(id=101,title='Adult Lighthouse',adult=True),MovieNameCandidate(id=102,title='Lighthouse',adult=False)],page=1,total_pages=1)
    provider.search_movie_names=titles
    result=asyncio.run(service.search(CatalogQuery(query='Lighthouse',include_adult=False)))
    assert [m.id for m in result.items]==[102]
    assert ('movie',101) not in provider.calls and store.get_movie(101) is None
