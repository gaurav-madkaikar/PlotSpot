import pytest
from movie_companion.accounts import AccountStore,AccountError
PASSWORD='A test-only long passphrase!'

class TestMailbox:
    __test__=False
    def __init__(self,origin):self.origin=origin;self.links=[]
    def require_available(self):pass
    def deliver(self,email,name,path):self.links.append(path);return path

def register_verified(store,name,password,previous):
    store.mail=TestMailbox(store.origin)
    result=store.register(name,password,previous,name.lower()+'@example.com')
    store.verify_email(result['preview_url'].split('=')[1])
    return store.login(name,password,previous)


def test_hashes_rotation_revocation_and_persistence(tmp_path):
    store=AccountStore(tmp_path/'accounts.db');guest=store.bootstrap(None)
    signed=register_verified(store,'FilmFan',PASSWORD,guest.token)
    assert signed.user['username']=='FilmFan' and signed.token!=guest.token
    assert store.session(guest.token) is None
    with store.connect() as db:
        hashed=db.execute('SELECT password_hash FROM users').fetchone()[0]
        tokens=[r[0] for r in db.execute('SELECT token_hash FROM sessions')]
    assert hashed.startswith('$argon2id$') and PASSWORD not in hashed and signed.token not in tokens
    reopened=AccountStore(store.path);assert reopened.session(signed.token).user==signed.user
    reopened.revoke(signed.token);assert store.session(signed.token) is None
    assert store.login('filmfan',PASSWORD,None).user==signed.user

def test_generic_wrong_credentials_and_normalized_username(tmp_path):
    store=AccountStore(tmp_path/'accounts.db');register_verified(store,'FilmFan',PASSWORD,None);messages=[]
    for name,password in [('filmfan','An incorrect test phrase!'),('Unknown',PASSWORD)]:
        with pytest.raises(AccountError) as exc:store.login(name,password,None)
        assert exc.value.status==401;messages.append(str(exc.value))
    assert messages[0]==messages[1]
    with pytest.raises(AccountError) as exc:store.register('FILMFAN',PASSWORD,None,'other@example.com')
    assert exc.value.status==409

def test_idle_absolute_and_guest_expiry(tmp_path):
    now=[100.];store=AccountStore(tmp_path/'accounts.db',clock=lambda:now[0])
    guest=store.bootstrap(None);now[0]+=601;assert store.session(guest.token) is None
    signed=register_verified(store,'viewer',PASSWORD,None);now[0]+=86401;assert store.session(signed.token) is None
    signed=store.login('viewer',PASSWORD,None)
    for _ in range(8):now[0]+=80000;store.session(signed.token)
    assert store.session(signed.token) is None

def test_rate_limit_survives_store_reopen(tmp_path):
    store=AccountStore(tmp_path/'accounts.db',attempt_limit=2)
    store.limit_attempt('test-client','viewer');store.limit_attempt('test-client','viewer')
    with pytest.raises(AccountError) as exc:AccountStore(store.path,attempt_limit=2).limit_attempt('test-client','viewer')
    assert exc.value.status==429


def test_normalized_username_variants_share_pair_limit(tmp_path):
    store=AccountStore(tmp_path/'accounts.db')
    for _ in range(10):store.limit_attempt('client','FilmFan')
    with pytest.raises(AccountError) as exc:store.limit_attempt('client','  ＦｉｌｍＦａｎ  ')
    assert exc.value.status==429


@pytest.mark.parametrize('password,valid',[('six123',True),('five!',False),('a'*128,True),('a'*129,False)])
def test_password_length_bounds(password,valid):
    from movie_companion.accounts import validate_password
    if valid:validate_password(password)
    else:
        with pytest.raises(AccountError) as exc:validate_password(password)
        assert exc.value.status==422
