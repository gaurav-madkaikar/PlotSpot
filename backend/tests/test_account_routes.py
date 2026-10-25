import pytest
from fastapi.testclient import TestClient
from movie_companion.main import app
from movie_companion.accounts import AccountStore
from movie_companion.account_routes import get_accounts
from test_accounts import PASSWORD,TestMailbox

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('FRAME_ACCOUNT_DB',str(tmp_path/'lifespan.db'))
    store=AccountStore(tmp_path/'private.db');store.mail=TestMailbox(store.origin);app.dependency_overrides[get_accounts]=lambda:store
    yield store
    app.dependency_overrides.pop(get_accounts,None)

def headers(client):
    response=client.get('/api/auth/session');assert response.status_code==200
    return {'Origin':'http://127.0.0.1:5173','X-CSRF-Token':response.json()['csrf_token']}

def register(client,name):
    h=headers(client)
    r=client.post('/api/auth/register',headers=h,json={'username':name,'password':PASSWORD,'email':name+'@example.com'})
    assert r.status_code==201
    assert client.get('/api/me/collection').status_code==401
    token=r.json()['preview_url'].split('=')[1]
    assert client.post('/api/auth/verify-email',headers=h,json={'token':token}).status_code==200
    r=client.post('/api/auth/login',headers=h,json={'username':name,'password':PASSWORD})
    assert r.status_code==200;return {**headers(client),'X-CSRF-Token':r.json()['csrf_token']}

def test_cookie_flags_rotation_logout_and_private_cache(setup):
    with TestClient(app) as client:
        # lifespan owns separate configured store, overridden routes use isolated DB.
        guest=client.get('/api/auth/session');old=client.cookies.get('frame_guest')
        h=register(client,'alice');new=client.cookies.get('frame_session')
        assert old!=new and setup.session(old) is None
        cookie=guest.headers['set-cookie'].lower();assert 'httponly' in cookie and 'samesite=strict' in cookie and 'path=/' in cookie
        r=client.get('/api/me/collection');assert r.status_code==200 and r.headers['cache-control']=='no-store'
        assert client.post('/api/auth/logout',headers=h,json={}).status_code==200
        assert setup.session(new) is None and client.get('/api/me/collection').status_code==401

@pytest.mark.parametrize('bad', ['missing','wrong','foreign-origin','null-origin','other-session','non-ascii'])
def test_csrf_and_origin_reject_before_mutation(setup,bad):
    client=TestClient(app);h=register(client,'alice')
    if bad=='non-ascii':h['X-CSRF-Token']=b'\xff'*43
    if bad=='missing':h.pop('X-CSRF-Token')
    if bad=='wrong':h['X-CSRF-Token']='x'*43
    if bad=='foreign-origin':h['Origin']='https://evil.example'
    if bad=='null-origin':h['Origin']='null'
    if bad=='other-session':h['X-CSRF-Token']=headers(TestClient(app))['X-CSRF-Token']
    r=client.put('/api/me/collection',headers=h,json={'revision':0,'saved':[157336],'watched':[],'collections':[]})
    assert r.status_code==403 and r.headers['cache-control']=='no-store'
    assert client.get('/api/me/collection').json()['snapshot']['saved']==[]

def test_two_owners_and_stale_snapshot_are_isolated(setup):
    a,b=TestClient(app),TestClient(app);ha=register(a,'alice');hb=register(b,'bravo')
    snapshot={'revision':0,'saved':[157336],'watched':[155],'collections':[]}
    assert a.put('/api/me/collection',headers=ha,json=snapshot).status_code==200
    assert b.get('/api/me/collection').json()['snapshot']['saved']==[]
    assert a.put('/api/me/collection',headers=ha,json={**snapshot,'saved':[155]}).status_code==409
    assert a.get('/api/me/collection').json()['snapshot']['saved']==[157336]
    assert b.put('/api/me/collection',headers=hb,json={**snapshot,'owner_id':a.get('/api/auth/session').json()['user']['id']}).status_code==422
    assert b.get('/api/me/collection').json()['snapshot']['saved']==[]

def test_bounds_and_validation_never_echo_password(setup):
    client=TestClient(app);h=headers(client)
    secret='tiny!'
    r=client.post('/api/auth/register',headers=h,json={'username':'alice','password':secret,'email':'alice@example.com'})
    assert r.status_code==422 and secret not in r.text
    assert r.headers['cache-control']=='no-store'
    assert client.post('/api/auth/login',headers=h,content='x'*131073).status_code==415
    assert client.post('/api/auth/login',headers={**h,'Content-Type':'application/json'},content='x'*131073).status_code==413
    assert client.post('/api/auth/login',headers=h,data={'username':'alice','password':PASSWORD}).status_code==415
    assert client.get('/api/me/collection').status_code==401


def test_session_reads_do_not_rewrite_rotated_cookie(setup):
    client=TestClient(app);guest=client.get('/api/auth/session');guest_cookie=client.cookies.get('frame_guest')
    repeated=client.get('/api/auth/session');assert 'set-cookie' not in repeated.headers
    h=register(client,'alice');signed=client.cookies.get('frame_session')
    assert 'set-cookie' not in client.get('/api/auth/session').headers
    # A late response from a previously missing/expired guest bootstrap can only
    # recreate the anonymous cookie; it cannot replace the signed-in cookie.
    client.cookies.set('frame_guest',guest_cookie,domain='testserver.local',path='/')
    assert client.get('/api/auth/session').json()['user']['username']=='alice'
    assert client.cookies.get('frame_session')==signed
    assert client.post('/api/auth/logout',headers=h,json={}).status_code==200
    assert client.get('/api/auth/session').json()['user'] is None


def test_secure_configuration_cookie_and_form_login_csrf(setup):
    setup.secure=True;setup.origin='https://frame.example';setup.cookie_name='__Host-frame_session';setup.guest_cookie_name='__Host-frame_guest'
    client=TestClient(app,base_url='https://frame.example')
    response=client.get('/api/auth/session');cookie=response.headers['set-cookie'].lower()
    assert 'secure' in cookie and '__host-frame_guest=' in cookie and 'domain=' not in cookie
    setup.mail.origin=setup.origin
    h={'Origin':setup.origin,'X-CSRF-Token':response.json()['csrf_token']}
    result=client.post('/api/auth/register',headers=h,json={'username':'alice','password':PASSWORD,'email':'alice@example.com'})
    assert result.status_code==201
    assert client.post('/api/auth/verify-email',headers=h,json={'token':result.json()['preview_url'].split('=')[1]}).status_code==200
    assert client.post('/api/auth/login',headers=h,json={'username':'alice','password':PASSWORD}).status_code==200
    assert '__Host-frame_session' in client.cookies
    assert client.post('/api/auth/login',headers={'Origin':'https://evil.example'},json={'username':'alice','password':PASSWORD}).status_code==403


def test_chunked_body_size_is_bounded_before_route():
    import asyncio
    from movie_companion.account_boundary import AccountBoundary
    async def run():
        called=[];messages=[]
        async def app(scope,receive,send):called.append(True)
        chunks=iter([{'type':'http.request','body':b'x'*65536,'more_body':True},
                     {'type':'http.request','body':b'x'*65537,'more_body':False}])
        async def receive():return next(chunks)
        async def send(message):messages.append(message)
        await AccountBoundary(app)({'type':'http','path':'/api/auth/login','method':'POST','headers':[(b'content-type',b'application/json')]},receive,send)
        assert not called and messages[0]['status']==413
        assert (b'cache-control',b'no-store') in messages[0]['headers']
    asyncio.run(run())


def test_expired_session_can_rebootstrap_and_login(setup):
    now=[100.];setup.clock=lambda:now[0]
    client=TestClient(app);h=register(client,'alice')
    assert client.post('/api/auth/logout',headers=h,json={}).status_code==200
    h=headers(client);now[0]+=601
    payload={'username':'alice','password':PASSWORD}
    assert client.post('/api/auth/login',headers=h,json=payload).status_code==401
    assert client.post('/api/auth/login',headers=headers(client),json=payload).status_code==200


def test_auth_throttle_blocks_before_password_work(setup,monkeypatch):
    client=TestClient(app);h=headers(client);setup.attempt_limit=1
    calls=[]
    def login(*args):calls.append(True);raise AccountError(401,'Username or password is incorrect.')
    from movie_companion.accounts import AccountError
    monkeypatch.setattr(setup,'login',login)
    data={'username':'viewer','password':PASSWORD}
    assert client.post('/api/auth/login',headers=h,json=data).status_code==401
    result=client.post('/api/auth/login',headers=h,json=data)
    assert result.status_code==429 and result.headers['retry-after']=='900' and calls==[True]


@pytest.mark.parametrize('password,status',[('six123',201),('five!',422)])
def test_registration_password_minimum_is_six(setup,password,status):
    client=TestClient(app);h=headers(client)
    result=client.post('/api/auth/register',headers=h,json={'username':'viewer','password':password,'email':'viewer@example.com'})
    assert result.status_code==status
    if status==201:
        token=result.json()['preview_url'].split('=')[1]
        assert client.post('/api/auth/verify-email',headers=h,json={'token':token}).status_code==200
        assert client.post('/api/auth/login',headers=h,json={'username':'viewer','password':password}).status_code==200
    else:
        assert password not in result.text
        with setup.connect() as db:assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
