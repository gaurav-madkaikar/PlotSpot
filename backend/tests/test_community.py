from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from movie_companion.main import app, get_content_store, get_question_service
from movie_companion.account_routes import get_accounts
from movie_companion.accounts import AccountStore
from movie_companion.community_store import CommunityStore
from movie_companion.community_contracts import ThreadInput, ReplyInput
from test_accounts import register_verified, PASSWORD

@pytest.fixture
def members(tmp_path,monkeypatch):
    monkeypatch.setenv('FRAME_ACCOUNT_DB',str(tmp_path/'lifespan.db'))
    store=AccountStore(tmp_path/'accounts.db');people=[]
    app.dependency_overrides[get_accounts]=lambda:store
    for name in ('alice','bravo','moderator'):
        signed=register_verified(store,name,PASSWORD,None)
        client=TestClient(app,headers={'Origin':store.origin,'X-CSRF-Token':signed.csrf})
        client.cookies.set(store.cookie_name,signed.token)
        people.append((client,signed.user['id']))
    store.moderator_ids=frozenset([people[2][1]])
    yield store,people
    app.dependency_overrides.clear()


def thread(client,*,spoilers=False,movie=157336,key=None,**changes):
    return client.post(f'/api/movies/{movie}/threads',json={'title':'A film worth discussing','body':'My interpretation of the film.','spoilers':spoilers,'request_key':key or str(uuid4()),**changes})

def reply(client,id,*,parent=None,spoilers=False,key=None):
    return client.post(f'/api/community/threads/{id}/replies',json={'body':'A thoughtful reply.','parent_id':parent,'spoilers':spoilers,'request_key':key or str(uuid4())})

@pytest.mark.parametrize('path',[
 '/api/movies/157336/features','/api/movies/157336/facts','/api/movies/157336/quiz',
 '/api/movies/157336/preparation?allow_spoilers=true','/api/movies/157336/threads',
 '/api/community/capabilities','/api/community/reports','/api/community/threads/1',
 '/api/community/threads/1/replies'])
def test_guest_reads_blocked_before_content_io(members,path):
    def forbidden():pytest.fail('Guests must not reach source/model/content dependencies')
    app.dependency_overrides[get_content_store]=forbidden
    app.dependency_overrides[get_question_service]=forbidden
    r=TestClient(app).get(path)
    assert r.status_code==401 and r.headers['cache-control']=='no-store' and r.headers['vary']=='Cookie'

@pytest.mark.parametrize('path,body',[
 ('/api/movies/157336/questions',{'question':'What happened?'}),
 ('/api/movies/157336/quiz/more',{'allow_spoilers':True}),
 ('/api/movies/157336/preparation',{'allow_spoilers':True}),
 ('/api/movies/157336/threads',{'title':'Guest','body':'Do not save this','request_key':str(uuid4())}),
 ('/api/community/threads/1/replies',{'body':'Guest','request_key':str(uuid4())}),
 ('/api/community/reports',{'kind':'thread','target_id':1,'reason':'spam'})])
def test_guest_writes_blocked(members,path,body):
    r=TestClient(app).post(path,json=body)
    assert r.status_code in (401,403) and r.headers['cache-control']=='no-store'
    with members[0].connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='community_threads'").fetchone()[0]==0

@pytest.mark.parametrize('kind',['threads','replies','reports'])
def test_member_csrf_required_before_mutation(members,kind):
    client,owner=members[1][0]
    r=client.post('/api/movies/157336/threads' if kind=='threads' else '/api/community/'+kind+'/1/delete' if kind=='replies' else '/api/community/reports',headers={'X-CSRF-Token':'bad'},json={})
    assert r.status_code==403 and r.headers['cache-control']=='no-store'


def test_threads_replies_owner_edit_and_revision_conflicts(members):
    a,owner=members[1][0];b,_=members[1][1]
    r=thread(a);assert r.status_code==201;id=r.json()['id']
    post=a.get(f'/api/community/threads/{id}').json()['thread'];assert post['can_edit'] and post['can_delete']
    other=b.get(f'/api/community/threads/{id}').json()['thread'];assert not other['can_edit'] and not other['can_delete']
    edit={'title':'Updated title','body':'Updated message','spoilers':False,'revision':1}
    assert b.patch(f'/api/community/threads/{id}',json=edit).status_code==403
    assert a.patch(f'/api/community/threads/{id}',json=edit).status_code==200
    assert a.patch(f'/api/community/threads/{id}',json=edit).status_code==409
    rid=reply(b,id).json()['id']
    assert a.patch(f'/api/community/replies/{rid}',json={'body':'No ownership','revision':1}).status_code==403
    assert b.patch(f'/api/community/replies/{rid}',json={'body':'My new reply','spoilers':False,'revision':1}).status_code==200
    assert a.post(f'/api/community/replies/{rid}/delete',json={'revision':2}).status_code==403
    assert b.post(f'/api/community/replies/{rid}/delete',json={'revision':2}).status_code==200
    tombstone=a.get(f'/api/community/threads/{id}/replies').json()['items'][0]
    assert tombstone['removed'] and tombstone['body'] is None and tombstone['author']=='Removed post'
    assert a.post(f'/api/community/threads/{id}/delete',json={'revision':2}).status_code==200
    assert b.get(f'/api/community/threads/{id}').status_code==404
    assert b.get(f'/api/community/threads/{id}/replies').status_code==404
    assert reply(b,id).status_code==404


def test_spoilers_redact_title_body_and_ancestor_replies(members):
    a,_=members[1][0];id=thread(a,spoilers=True,title='Ending reveal',body='Secret ending').json()['id']
    post=a.get('/api/movies/157336/threads').json()['items'][0]
    assert post['title']=='Spoiler discussion' and post['body'] is None and post['spoiler_locked']
    rid=reply(a,id).json()['id']
    assert a.get(f'/api/community/threads/{id}/replies').json()['items'][0]['body'] is None
    assert a.get(f'/api/community/threads/{id}?allow_spoilers=true').json()['thread']['body']=='Secret ending'
    safe=thread(a).json()['id'];parent=reply(a,safe,spoilers=True).json()['id'];child=reply(a,safe,parent=parent).json()['id']
    # Even editing a child's label cannot bypass an ancestor's spoiler flag.
    assert a.patch(f'/api/community/replies/{child}',json={'body':'Ending','spoilers':False,'revision':1}).status_code==200
    posts=a.get(f'/api/community/threads/{safe}/replies').json()['items']
    assert all(p['body'] is None and p['spoiler_locked'] for p in posts)


def test_idempotency_parent_scope_and_depth_limits(members):
    a,_=members[1][0];key=str(uuid4());first=thread(a,key=key)
    assert thread(a,key=key).json()==first.json()
    assert thread(a,key=key,body='Changed').status_code==409
    id=first.json()['id'];other=thread(a).json()['id'];parent=None
    for _ in range(4):
        r=reply(a,id,parent=parent);assert r.status_code==201;parent=r.json()['id']
    assert reply(a,id,parent=parent).status_code==422
    assert reply(a,other,parent=parent).status_code==422
    key=str(uuid4());first=reply(a,id,key=key)
    assert reply(a,id,key=key).json()==first.json()
    assert reply(a,id,key=key,spoilers=True).status_code==409


def test_reports_do_not_hide_and_moderation_requires_configured_role(members):
    a,_=members[1][0];b,_=members[1][1];mod,mid=members[1][2]
    id=thread(a,spoilers=True).json()['id'];body={'kind':'thread','target_id':id,'reason':'spam','details':'May quote an ending'}
    report=b.post('/api/community/reports',json=body);assert report.status_code==201;rid=report.json()['id']
    assert b.post('/api/community/reports',json=body).json()==report.json()
    assert a.post('/api/community/reports',json=body).status_code==422
    assert b.get(f'/api/community/threads/{id}').status_code==200
    assert b.get('/api/community/reports').status_code==403
    assert b.post(f'/api/community/reports/{rid}/review',json={'action':'hide','revision':1}).status_code==403
    assert mod.get('/api/community/capabilities').json()['moderator']
    protected=mod.get('/api/community/reports').json()['items'][0]
    assert protected['body'] is None and protected['details'] is None and protected['title'] is None
    assert mod.get('/api/community/reports?allow_spoilers=true').json()['items'][0]['details']==body['details']
    assert mod.post(f'/api/community/reports/{rid}/review',json={'action':'hide','revision':1}).status_code==200
    assert a.get(f'/api/community/threads/{id}').status_code==404
    reviewed=mod.get('/api/community/reports?state=resolved').json()['items'][0]
    assert reviewed['content_state']=='hidden' and reviewed['revision']==2
    assert mod.post(f'/api/community/reports/{rid}/review',json={'action':'restore','revision':1}).status_code==409
    assert mod.post(f'/api/community/reports/{rid}/review',json={'action':'restore','revision':2}).status_code==200
    assert a.get(f'/api/community/threads/{id}').status_code==200
    with members[0].connect() as db:assert [r['action'] for r in db.execute('SELECT action FROM community_audit')]==['hide','restore']


def test_pagination_rate_limits_and_restart(members):
    store=members[0];a,owner=members[1][0];community=CommunityStore(store)
    for i in range(22):community.create_thread(157336,owner,ThreadInput(title=f'Topic {i}',body='A message',request_key=uuid4()))
    first=a.get('/api/movies/157336/threads').json();second=a.get('/api/movies/157336/threads?page=2').json()
    assert len(first['items'])==20 and len(second['items'])==2 and first['has_more'] and not second['has_more']
    assert CommunityStore(AccountStore(store.path)).threads(157336,owner,1,False)['total']==22
    for _ in range(30):community.limit_write(owner)
    r=thread(a);assert r.status_code==429 and int(r.headers['retry-after'])>0
    id=first['items'][0]['id']
    for _ in range(32):community.create_reply(id,owner,ReplyInput(body='Reply',request_key=uuid4()))
    assert len(a.get(f'/api/community/threads/{id}/replies').json()['items'])==30
    assert len(a.get(f'/api/community/threads/{id}/replies?page=2').json()['items'])==2

@pytest.mark.parametrize('changes',[{'title':' '},{'body':'x'*5001},{'body':'control\u0001'},{'spoilers':'true'},{'owner_id':'fake'},{'role':'moderator'}])
def test_validation_never_echoes_posts_and_cannot_grant_roles(members,changes):
    a,_=members[1][0];r=thread(a,**changes)
    assert r.status_code==422 and 'My interpretation' not in r.text and 'control' not in r.text


def test_unknown_movie_and_member_ai_csrf(members):
    a,_=members[1][0]
    assert thread(a,movie=999999).status_code==404
    for path in ('questions','quiz/more','preparation'):
        assert a.post('/api/movies/157336/'+path,json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert a.get('/api/movies/157336').status_code==200


def test_rate_limit_precedes_external_movie_validation(members,monkeypatch):
    a,owner=members[1][0];community=CommunityStore(members[0])
    for _ in range(30):community.limit_write(owner)
    async def forbidden(*args):pytest.fail('Throttled users cannot trigger provider reads')
    monkeypatch.setattr('movie_companion.community_routes.valid_movie',forbidden)
    assert thread(a,movie=999999).status_code==429
