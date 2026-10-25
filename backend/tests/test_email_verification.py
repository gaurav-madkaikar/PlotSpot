import sqlite3
import pytest
from movie_companion.accounts import AccountStore, AccountError, PASSWORDS, token_hash
from movie_companion.verification_mail import VerificationMail, MailUnavailable
from test_accounts import PASSWORD, TestMailbox


def make_store(tmp_path, now=None):
    mail=TestMailbox('http://127.0.0.1:5173')
    return AccountStore(tmp_path/'accounts.db',mail=mail,clock=(lambda:now[0]) if now else __import__('time').time)


def token(receipt):return receipt['preview_url'].split('=')[1]


def test_registration_requires_verification_and_stores_only_hash(tmp_path):
    store=make_store(tmp_path);guest=store.bootstrap(None)
    result=store.register('viewer',PASSWORD,guest.token,'Viewer@EXAMPLE.com')
    assert store.session(guest.token).user is None
    with store.connect() as db:
        row=db.execute('SELECT * FROM users').fetchone()
        verification=db.execute('SELECT * FROM email_verifications').fetchone()
        assert row['email']=='Viewer@example.com' and row['email_key']=='viewer@example.com'
        assert row['verified_at'] is None and verification['token_hash']==token_hash(token(result))
        assert token(result) not in str(dict(verification))
    with pytest.raises(AccountError) as exc:store.login('viewer',PASSWORD,guest.token)
    assert exc.value.status==409
    assert store.verify_email(token(result))=={'status':'verified'}
    signed=store.login('viewer',PASSWORD,guest.token)
    assert signed.user['username']=='viewer' and store.session(guest.token) is None
    with pytest.raises(AccountError) as exc:store.verify_email(token(result))
    assert exc.value.status==400


def test_expiry_resend_rotation_and_cooldown_are_persistent(tmp_path):
    now=[100.];store=make_store(tmp_path,now)
    first=store.register('viewer',PASSWORD,None,'viewer@example.com')
    with pytest.raises(AccountError) as exc:store.resend('viewer',PASSWORD)
    assert exc.value.status==429
    now[0]+=61
    second=store.resend('viewer',PASSWORD)
    with pytest.raises(AccountError):store.verify_email(token(first))
    now[0]+=1800
    with pytest.raises(AccountError):store.verify_email(token(second))
    reopened=AccountStore(store.path,clock=lambda:now[0],mail=store.mail)
    third=reopened.resend('viewer',PASSWORD)
    reopened.verify_email(token(third))
    with pytest.raises(AccountError) as exc:store.resend('viewer',PASSWORD)
    assert exc.value.status==409


@pytest.mark.parametrize('email',['bad', 'a@localhost', 'a@example.com\r\nBcc: victim@example.com', 'a b@example.com', 'a@@example.com'])
def test_invalid_email_is_rejected_without_reserving_account(tmp_path,email):
    store=make_store(tmp_path)
    with pytest.raises(AccountError) as exc:store.register('viewer',PASSWORD,None,email)
    assert exc.value.status==422
    with store.connect() as db:assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0


def test_delivery_failure_rolls_back_signup_and_preserves_resend_link(tmp_path):
    now=[100.];store=make_store(tmp_path,now)
    original=store.mail.deliver
    def fail(*args):raise MailUnavailable('Test delivery unavailable.')
    store.mail.deliver=fail
    with pytest.raises(AccountError) as exc:store.register('viewer',PASSWORD,None,'viewer@example.com')
    assert exc.value.status==503
    with store.connect() as db:assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0
    store.mail.deliver=original;receipt=store.register('viewer',PASSWORD,None,'viewer@example.com')
    now[0]+=61;store.mail.deliver=fail
    with pytest.raises(AccountError):store.resend('viewer',PASSWORD)
    assert store.verify_email(token(receipt))=={'status':'verified'}


def test_legacy_account_migration_keeps_owner_hash_and_sessions(tmp_path):
    path=tmp_path/'legacy.db';owner='a'*32
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE users (id TEXT PRIMARY KEY,username TEXT NOT NULL,username_key TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL)')
        db.execute('INSERT INTO users VALUES (?,?,?,?)',(owner,'legacy','legacy',PASSWORDS.hash(PASSWORD)))
    store=AccountStore(path)
    assert store.login('legacy',PASSWORD,None).user['id']==owner
    reopened=AccountStore(path)
    with reopened.connect() as db:
        row=db.execute('SELECT * FROM users').fetchone()
        assert row['email'] is None and row['verified_at'] is None


@pytest.mark.parametrize('origin',['https://plotspot.example','http://plotspot.example','https://localhost'])
def test_preview_cannot_be_configured_for_deployment(origin):
    with pytest.raises(ValueError):VerificationMail(mode='preview',origin=origin)


def test_disabled_delivery_fails_before_signup(tmp_path):
    store=AccountStore(tmp_path/'accounts.db')
    with pytest.raises(AccountError) as exc:store.register('viewer',PASSWORD,None,'viewer@example.com')
    assert exc.value.status==503
    with store.connect() as db:assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0


def test_smtp_uses_tls_and_never_exposes_a_preview(monkeypatch):
    calls=[]
    class SMTP:
        def __init__(self,*args,**kwargs):calls.append(('connect',kwargs['timeout']))
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def ehlo(self):calls.append(('ehlo',))
        def starttls(self,context):calls.append(('tls',context.check_hostname))
        def login(self,*args):calls.append(('login',))
        def send_message(self,msg):
            calls.append(('send',))
            assert msg['Subject']=='Verify your PlotSpot email' and 'expires in 30 minutes' in msg.get_content()
    monkeypatch.setattr('movie_companion.verification_mail.smtplib.SMTP',SMTP)
    mail=VerificationMail(mode='smtp',origin='https://plotspot.example',host='smtp.example.com',sender='sender@example.com',username='test',password='test')
    assert mail.deliver('viewer@example.com','viewer','/account#verify='+'x'*43) is None
    assert calls==[('connect',10),('ehlo',),('tls',True),('ehlo',),('login',),('send',)]


def test_smtp_resend_never_holds_shared_database_lock(tmp_path):
    now=[100.];store=make_store(tmp_path,now)
    store.register('viewer',PASSWORD,None,'viewer@example.com');guest=store.bootstrap(None)
    now[0]+=61
    def deliver(*args):
        # A distinct connection represents another user's concurrent request.
        assert store.session(guest.token).user is None
        with pytest.raises(AccountError) as exc:store.resend('viewer',PASSWORD)
        assert exc.value.status==429
        return args[-1]
    store.mail.deliver=deliver
    result=store.resend('viewer',PASSWORD)
    assert store.verify_email(token(result))=={'status':'verified'}


def test_old_link_can_be_verified_while_resend_is_delivering(tmp_path):
    now=[100.];store=make_store(tmp_path,now)
    old=store.register('viewer',PASSWORD,None,'viewer@example.com');now[0]+=61
    def deliver(*args):store.verify_email(token(old));return args[-1]
    store.mail.deliver=deliver
    with pytest.raises(AccountError) as exc:store.resend('viewer',PASSWORD)
    assert exc.value.status==409
    assert store.login('viewer',PASSWORD,None).user['username']=='viewer'
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM verification_sends').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM email_verifications').fetchone()[0]==0
