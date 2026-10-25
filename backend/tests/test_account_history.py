from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from movie_companion.main import app
from movie_companion.history_routes import history_content
from movie_companion.content_store import ContentStore
from movie_companion.accounts import AccountStore
from test_account_routes import setup, register, headers
from test_content_store import fixture_collection


def event(movie_id=157336):return {'event_id':str(uuid4()),'movie_id':movie_id}

def owner_headers(client,auth):return {**auth,'X-Account-Owner':client.get('/api/auth/session').json()['user']['id']}

@pytest.fixture
def bank(tmp_path):
    source,(quiz,facts)=fixture_collection()
    store=ContentStore(tmp_path/'quiz.db')
    store.publish(157336,version='v1',source_revision=source.revision,quiz=quiz,facts=facts)
    quiz.prepared_at=store.load(157336)['prepared_at']
    app.dependency_overrides[history_content]=lambda:store
    yield store,quiz
    app.dependency_overrides.pop(history_content,None)


def completed(quiz,**changes):
    return {**event(),'content_version':'v1','content_prepared_at':quiz.prepared_at,'allow_spoilers':True,'answers':{q.id:q.correct_index for q in quiz.items},**changes}


def test_visits_record_every_page_visit_idempotently_and_paginate(setup):
    client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    first=event();response=client.post('/api/me/history/movies',headers=auth,json=first)
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert response.json()['item']['title']=='Interstellar'
    assert client.post('/api/me/history/movies',headers=auth,json=first).json()==response.json()
    assert client.post('/api/me/history/movies',headers=auth,json={**first,'movie_id':27205}).status_code==409
    assert client.post('/api/me/history/movies',headers=auth,json=event()).status_code==200
    assert client.post('/api/me/history/movies',headers=auth,json=event(27205)).status_code==200
    page=client.get('/api/me/history/movies?page_size=2').json()
    assert page['total']==3 and page['total_pages']==2 and page['items'][0]['title']=='Inception'
    assert client.get('/api/me/history/movies?page_size=2&page=2').json()['items'][0]['id']==first['event_id']
    # Movie API reads and feature reads do not themselves create visit events.
    client.get('/api/movies/157336');client.get('/api/movies/157336/features')
    assert client.get('/api/me/history/movies').json()['total']==3


def test_history_toggle_is_enforced_and_legacy_settings_preserve_it(setup):
    client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    body=client.get('/api/auth/session').json()['user']['preferences']
    assert client.post('/api/me/history/movies',headers=auth,json=event()).status_code==200
    changed=client.put('/api/me/preferences',headers=auth,json={**body,'track_movie_history':False})
    assert changed.status_code==200
    result=client.post('/api/me/history/movies',headers=auth,json=event())
    assert result.json()['status']=='disabled' and result.json()['item'] is None
    assert client.get('/api/me/history/movies').json()['total']==1
    legacy=changed.json()['user']['preferences'];legacy.pop('track_movie_history')
    assert client.put('/api/me/preferences',headers=auth,json=legacy).json()['user']['preferences']['track_movie_history'] is False


def test_server_scores_round_and_excludes_interpretations(setup,bank):
    store,quiz=bank
    client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    body=completed(quiz)
    factual=[q for q in quiz.items if q.kind!='interpretation']
    body['answers'][factual[0].id]=(factual[0].correct_index+1)%4
    for q in quiz.items:
        if q.kind=='interpretation':body['answers'][q.id]=(q.correct_index+1)%4
    response=client.post('/api/me/history/quizzes',headers=auth,json=body)
    assert response.status_code==200
    item=response.json()['item']
    assert item['score']==len(factual)-1 and item['scored_questions']==len(factual) and item['total_questions']==len(quiz.items)
    assert 'answers' not in item and 'question' not in item
    # Retries survive shared-bank version changes and do not count another round.
    source,(new_quiz,facts)=fixture_collection()
    store.publish(157336,version='v2',source_revision=source.revision,quiz=new_quiz,facts=facts)
    assert client.post('/api/me/history/quizzes',headers=auth,json=body).json()==response.json()
    assert client.post('/api/me/history/quizzes',headers=auth,json={**body,'event_id':str(uuid4())}).status_code==409
    assert client.get('/api/me/history/quizzes').json()['total']==1


@pytest.mark.parametrize('change',['incomplete','extra','bool','score','version','spoilers'])
def test_bad_or_incomplete_round_cannot_be_recorded(setup,bank,change):
    _,quiz=bank;client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    body=completed(quiz)
    if change=='incomplete':body['answers'].pop(next(iter(body['answers'])))
    if change=='extra':body['answers']['unknown-question']=0
    if change=='bool':body['answers'][next(iter(body['answers']))]=True
    if change=='score':body['score']=100
    if change=='version':body['content_version']='old'
    if change=='spoilers':body['allow_spoilers']=False
    assert client.post('/api/me/history/quizzes',headers=auth,json=body).status_code in (403,409,422)
    assert client.get('/api/me/history/quizzes').json()['total']==0


def test_owner_isolation_and_independent_clear(setup,bank):
    _,quiz=bank;a,b=TestClient(app),TestClient(app)
    ha=owner_headers(a,register(a,'first_viewer'));hb=owner_headers(b,register(b,'second_viewer'))
    assert a.post('/api/me/history/movies',headers=ha,json=event()).status_code==200
    assert a.post('/api/me/history/quizzes',headers=ha,json=completed(quiz)).status_code==200
    assert b.get('/api/me/history/movies').json()['items']==[]
    assert b.request('DELETE','/api/me/history/movies',headers=hb,json={}).status_code==200
    assert a.get('/api/me/history/movies').json()['total']==1
    assert a.request('DELETE','/api/me/history/movies',headers=ha,json={}).status_code==200
    assert a.get('/api/me/history/movies').json()['total']==0
    assert a.get('/api/me/history/quizzes').json()['total']==1


def test_auth_csrf_wrong_owner_and_invalid_movie(setup):
    guest=TestClient(app)
    assert guest.get('/api/me/history/movies').status_code==401
    assert guest.post('/api/me/history/movies',headers=headers(guest),json=event()).status_code==401
    client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    for bad in [{'Origin':setup.origin}, {**auth,'Origin':'https://example.com'}, {**auth,'X-Account-Owner':'f'*32}]:
        assert client.post('/api/me/history/movies',headers=bad,json=event()).status_code in (401,403)
    assert client.post('/api/me/history/movies',headers=auth,json=event(999999)).status_code==404
    assert client.post('/api/me/history/movies',headers=auth,json={**event(),'title':'Forged title'}).status_code==422
    assert client.get('/api/me/history/movies').json()['total']==0
    assert client.get('/api/me/history/quizzes?page_size=41').status_code==422


def test_preference_migration_preserves_existing_settings(setup):
    client=TestClient(app);register(client,'viewer')
    owner=client.get('/api/auth/session').json()['user']['id']
    with setup.connect() as db:
        db.execute('DROP TABLE account_preferences')
        db.execute('CREATE TABLE account_preferences(owner TEXT PRIMARY KEY,revision INTEGER,allow_spoilers INTEGER,include_adult INTEGER)')
        db.execute('INSERT INTO account_preferences VALUES (?,?,?,?)',(owner,7,1,0))
    reopened=AccountStore(setup.path)
    prefs=reopened.session(client.cookies.get('frame_session')).user['preferences']
    assert prefs=={'revision':7,'allow_spoilers':True,'include_adult':False,'track_movie_history':True}


def test_bank_refresh_with_same_version_rejects_a_stale_new_round(setup,bank):
    store,quiz=bank;client=TestClient(app);auth=owner_headers(client,register(client,'viewer'))
    body=completed(quiz)
    source,(new_quiz,facts)=fixture_collection()
    store.publish(157336,version='v1',source_revision=source.revision,quiz=new_quiz,facts=facts)
    assert client.post('/api/me/history/quizzes',headers=auth,json=body).status_code==409
    assert client.get('/api/me/history/quizzes').json()['total']==0
