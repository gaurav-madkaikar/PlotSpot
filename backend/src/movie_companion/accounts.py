"""Local credentials and opaque, revocable sessions. No personal data goes to AI."""
from contextlib import contextmanager
from dataclasses import dataclass,field
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import unicodedata
from urllib.parse import urlsplit
from uuid import uuid4

from .account_preferences import PREFERENCES_TABLE, read_preferences
from .verification_mail import VerificationMail, MailUnavailable, normalized_email

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError

DEFAULT_PATH=Path(__file__).resolve().parents[2]/'data/private/accounts/accounts.db'
PASSWORDS=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1)
SESSION_SECONDS=7*86400
IDLE_SECONDS=86400
GUEST_SECONDS=600


class AccountError(ValueError):
    def __init__(self,status,message,*,retry_after=900):
        self.status=status;self.retry_after=retry_after
        super().__init__(message)


def username_key(value):
    name=unicodedata.normalize('NFKC',value).strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,31}',name):
        raise AccountError(422,'Use 3–32 letters, numbers, dots, hyphens or underscores for your username.')
    return name,name.casefold()


def validate_password(password):
    if not isinstance(password,str) or not 6<=len(password)<=128 or len(password.encode('utf-8'))>512:
        raise AccountError(422,'Use a password between 6 and 128 characters.')


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Session:
    token: str=field(repr=False)
    csrf: str=field(repr=False)
    user: dict|None

    def envelope(self):return {'user':self.user,'csrf_token':self.csrf}


class AccountStore:
    def __init__(self,path=DEFAULT_PATH,*,clock=time.time,origin='http://127.0.0.1:5173',secure=False,attempt_limit=30, mail=None, moderator_ids=()):
        parts=urlsplit(origin)
        if (parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password
                or parts.path or parts.query or parts.fragment or not 1<=attempt_limit<=100
                or parts.scheme=='https' and not secure
                or parts.scheme=='http' and (parts.hostname not in ('127.0.0.1','localhost','::1') or secure)):
            raise ValueError('Configure an exact app origin and matching HTTPS cookie mode.')
        self.path=Path(path);self.clock=clock;self.origin=origin;self.secure=secure;self.attempt_limit=attempt_limit
        self.moderator_ids=frozenset(moderator_ids)
        if len(self.moderator_ids)>25 or any(not re.fullmatch(r'[a-f0-9]{32}',id) for id in self.moderator_ids):raise ValueError('Configure moderator account UUIDs, never usernames or client roles.')
        self.mail=mail or VerificationMail(origin=origin)
        if self.mail.origin != origin:raise ValueError('Mail and account origins must match.')
        self.cookie_name='__Host-frame_session' if secure else 'frame_session'
        self.guest_cookie_name='__Host-frame_guest' if secure else 'frame_guest'
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.dummy_hash=PASSWORDS.hash(secrets.token_urlsafe(32))
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT NOT NULL, username_key TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)')
            columns={row['name'] for row in db.execute('PRAGMA table_info(users)')}
            for name,kind in [('email','TEXT'),('email_key','TEXT'),('verified_at','REAL')]:
                if name not in columns:db.execute(f'ALTER TABLE users ADD COLUMN {name} {kind}')
            db.execute(PREFERENCES_TABLE)
            if 'track_movie_history' not in {r['name'] for r in db.execute('PRAGMA table_info(account_preferences)')}:
                db.execute('ALTER TABLE account_preferences ADD COLUMN track_movie_history INTEGER NOT NULL DEFAULT 1 CHECK(track_movie_history IN (0,1))')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users(email_key) WHERE email_key IS NOT NULL')
            db.execute('CREATE TABLE IF NOT EXISTS email_verifications (owner TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT UNIQUE NOT NULL, expires REAL NOT NULL, sent_at REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS verification_sends (owner TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, request_id TEXT NOT NULL, started REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, owner TEXT REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL, last_seen REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS auth_limits (key TEXT PRIMARY KEY, began REAL NOT NULL, count INTEGER NOT NULL)')
        self.path.chmod(0o600)

    @classmethod
    def configured(cls):
        secure=os.getenv('FRAME_SECURE_COOKIES','false').lower()
        if secure not in ('true','false'):raise ValueError('FRAME_SECURE_COOKIES must be true or false')
        origin=os.getenv('FRAME_APP_ORIGIN','http://127.0.0.1:5173')
        return cls(os.getenv('FRAME_ACCOUNT_DB',str(DEFAULT_PATH)),origin=origin,secure=secure=='true',mail=VerificationMail.configured(origin),moderator_ids=[id.strip() for id in os.getenv('PLOTSPOT_MODERATOR_IDS','').split(',') if id.strip()])

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
            yield db;db.commit()
        except BaseException:
            db.rollback();raise
        finally:db.close()

    def limit_attempt(self,client,username):
        now=self.clock()
        keys=[(token_hash('client:'+client),self.attempt_limit),
              (token_hash('pair:'+client+':'+unicodedata.normalize('NFKC',username).strip().casefold()),min(10,self.attempt_limit))]
        with self.connect() as db:
            db.execute('DELETE FROM auth_limits WHERE began<=?',(now-900,))
            for key,limit in keys:
                row=db.execute('SELECT count FROM auth_limits WHERE key=?',(key,)).fetchone()
                if row and row['count']>=limit:raise AccountError(429,'Too many sign-in attempts. Try again in 15 minutes.')
            if db.execute('SELECT COUNT(*) FROM auth_limits').fetchone()[0]>=10000:
                raise AccountError(429,'Sign-in is busy. Try again later.')
            for key,_ in keys:
                db.execute('INSERT INTO auth_limits VALUES (?,?,1) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,now))

    def session(self,token):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):return None
        now=self.clock()
        with self.connect() as db:
            row=db.execute('SELECT s.*,u.username FROM sessions s LEFT JOIN users u ON u.id=s.owner WHERE token_hash=?',(token_hash(token),)).fetchone()
            if row is None:return None
            if row['expires']<=now or row['owner'] and row['last_seen']+IDLE_SECONDS<=now:
                db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token),));return None
            db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?',(now,token_hash(token)))
            user=None if row['owner'] is None else {'id':row['owner'],'username':row['username'],'preferences':read_preferences(db,row['owner']).model_dump()}
            return Session(token,row['csrf'],user)

    def _issue(self,db,owner,username,previous):
        now=self.clock();token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<=? OR (owner IS NOT NULL AND last_seen<=?)',(now,now-IDLE_SECONDS))
        if previous:db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(previous),))
        if owner:
            # Keep at most five device sessions per account.
            rows=db.execute('SELECT token_hash FROM sessions WHERE owner=? ORDER BY last_seen DESC,token_hash',(owner,)).fetchall()
            for row in rows[4:]:db.execute('DELETE FROM sessions WHERE token_hash=?',(row['token_hash'],))
        elif db.execute('SELECT COUNT(*) FROM sessions WHERE owner IS NULL').fetchone()[0]>=5000:
            raise AccountError(429,'Account access is busy. Try again shortly.')
        db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(token_hash(token),csrf,owner,now+(SESSION_SECONDS if owner else GUEST_SECONDS),now))
        return Session(token,csrf,None if owner is None else {'id':owner,'username':username,'preferences':read_preferences(db,owner).model_dump()})

    def bootstrap(self,token):
        current=self.session(token)
        if current:return current
        with self.connect() as db:return self._issue(db,None,None,None)

    def _mail_receipt(self,email,name,token):
        path='/account#verify='+token
        try:preview=self.mail.deliver(email,name,path)
        except MailUnavailable as exc:raise AccountError(503,str(exc)) from None
        return {'status':'verification_required','preview_url':preview}

    def register(self,username,password,previous,email):
        name,key=username_key(username);validate_password(password)
        try:address=normalized_email(email)
        except ValueError as exc:raise AccountError(422,str(exc)) from None
        try:self.mail.require_available()
        except MailUnavailable as exc:raise AccountError(503,str(exc)) from None
        hashed=PASSWORDS.hash(password);now=self.clock();token=secrets.token_urlsafe(32)
        # Local-part comparison is case-insensitive by application policy; no
        # provider-specific dot/plus stripping, and the delivery spelling is kept.
        email_key=address.casefold()
        with self.connect() as db:
            if db.execute('SELECT 1 FROM users WHERE username_key=? OR email_key=?',(key,email_key)).fetchone():
                raise AccountError(409,'These account details are unavailable. Try signing in or use different details.')
            owner=uuid4().hex
            db.execute('INSERT INTO users (id,username,username_key,password_hash,email,email_key) VALUES (?,?,?,?,?,?)',(owner,name,key,hashed,address,email_key))
            db.execute('INSERT INTO email_verifications VALUES (?,?,?,?)',(owner,token_hash(token),now+1800,now))
        try:return self._mail_receipt(address,name,token)
        except AccountError:
            # Failed delivery cannot leave a reserved username/email behind.
            with self.connect() as db:
                db.execute('DELETE FROM users WHERE id=? AND verified_at IS NULL',(owner,))
            raise

    def _credentials(self,username,password):
        _,key=username_key(username);validate_password(password)
        with self.connect() as db:row=db.execute('SELECT * FROM users WHERE username_key=?',(key,)).fetchone()
        try:valid=PASSWORDS.verify(row['password_hash'] if row else self.dummy_hash,password)
        except (VerificationError,InvalidHashError):valid=False
        if not valid or row is None:raise AccountError(401,'Username or password is incorrect.')
        return row

    def resend(self,username,password):
        row=self._credentials(username,password);now=self.clock();token=secrets.token_urlsafe(32)
        if row['email'] is None or row['verified_at'] is not None:
            raise AccountError(409,'This account can already sign in.')
        try:self.mail.require_available()
        except MailUnavailable as exc:raise AccountError(503,str(exc)) from None
        request_id=uuid4().hex
        with self.connect() as db:
            old=db.execute('SELECT * FROM email_verifications WHERE owner=?',(row['id'],)).fetchone()
            reserved=db.execute('SELECT started FROM verification_sends WHERE owner=?',(row['id'],)).fetchone()
            if reserved and reserved['started']+120>now:
                raise AccountError(429,'A verification email is already being prepared. Try again shortly.',retry_after=60)
            if old and old['sent_at']+60>now:
                raise AccountError(429,'Wait a minute before requesting another verification link.',retry_after=max(1,int(old['sent_at']+60-now+0.999)))
            db.execute('INSERT INTO verification_sends VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET request_id=excluded.request_id,started=excluded.started',(row['id'],request_id,now))
        try:
            # SMTP must never hold the shared SQLite write lock. Reserve per
            # owner first; the old verification link survives failed delivery.
            receipt=self._mail_receipt(row['email'],row['username'],token)
            with self.connect() as db:
                reserved=db.execute('SELECT request_id FROM verification_sends WHERE owner=?',(row['id'],)).fetchone()
                current=db.execute('SELECT verified_at FROM users WHERE id=?',(row['id'],)).fetchone()
                if not reserved or reserved['request_id']!=request_id:
                    raise AccountError(409,'A newer verification request is being prepared. Try again shortly.')
                if current is None or current['verified_at'] is not None:
                    raise AccountError(409,'This account can already sign in.')
                completed=self.clock()
                db.execute('INSERT INTO email_verifications VALUES (?,?,?,?) ON CONFLICT(owner) DO UPDATE SET token_hash=excluded.token_hash,expires=excluded.expires,sent_at=excluded.sent_at',(row['id'],token_hash(token),completed+1800,completed))
            return receipt
        finally:
            with self.connect() as db:
                db.execute('DELETE FROM verification_sends WHERE owner=? AND request_id=?',(row['id'],request_id))

    def verify_email(self,token):
        invalid='This verification link has expired or was already used. Request a new link from Sign in.'
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AccountError(400,invalid)
        now=self.clock()
        with self.connect() as db:
            row=db.execute('SELECT * FROM email_verifications WHERE token_hash=?',(token_hash(token),)).fetchone()
            if row is None or row['expires']<=now:raise AccountError(400,invalid)
            db.execute('UPDATE users SET verified_at=? WHERE id=?',(now,row['owner']))
            db.execute('DELETE FROM email_verifications WHERE owner=?',(row['owner'],))
        return {'status':'verified'}

    def login(self,username,password,previous):
        row=self._credentials(username,password)
        if row['email'] is not None and row['verified_at'] is None:
            raise AccountError(409,'Verify your email before signing in. You can request a new verification link below.')
        rehash=PASSWORDS.hash(password) if PASSWORDS.check_needs_rehash(row['password_hash']) else None
        with self.connect() as db:
            if rehash:db.execute('UPDATE users SET password_hash=? WHERE id=?',(rehash,row['id']))
            return self._issue(db,row['id'],row['username'],previous)

    def revoke(self,token):
        if token:
            with self.connect() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token),))
