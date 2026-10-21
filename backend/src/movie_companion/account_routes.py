"""Session-derived ownership and synchronizer CSRF at the private HTTP boundary."""
import secrets
import re
from typing import Annotated
from fastapi import APIRouter,Depends,Request,Response
from pydantic import Field
from .account_preferences import AccountPreferences, PreferencesUpdate, save_preferences
from .accounts import AccountStore,AccountError,Session,GUEST_SECONDS,SESSION_SECONDS
from .content_proposals import StrictRecord
from .personal_contracts import PersonalSnapshot,ImportRequest
from .personal_store import PersonalStore

router=APIRouter()

class Credentials(StrictRecord):
    username:str=Field(min_length=3,max_length=128)
    password:str=Field(min_length=6,max_length=128,repr=False)

class Registration(Credentials):
    email:str=Field(min_length=3,max_length=254,repr=False)

class VerificationReceipt(StrictRecord):
    status:str=Field(pattern=r'^verification_required$')
    preview_url:str|None=Field(default=None,pattern=r'^/account#verify=[A-Za-z0-9_-]{43}$',repr=False)

class VerificationRequest(StrictRecord):
    token:str=Field(pattern=r'^[A-Za-z0-9_-]{43}$',repr=False)

class VerifiedView(StrictRecord):
    status:str=Field(pattern=r'^verified$')

class UserView(StrictRecord):
    preferences:AccountPreferences=Field(default_factory=AccountPreferences)
    id:str=Field(pattern=r'^[a-f0-9]{32}$')
    username:str=Field(min_length=3,max_length=32)

class SessionView(StrictRecord):
    user:UserView|None
    csrf_token:str=Field(pattern=r'^[A-Za-z0-9_-]{43}$')

class LogoutRequest(StrictRecord):pass

class PersonalView(StrictRecord):
    owner_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    snapshot:PersonalSnapshot


def get_accounts(request:Request):
    accounts=getattr(request.app.state,'accounts',None)
    if accounts is None:raise AccountError(503,'Account access is unavailable. Try again shortly.')
    return accounts

def resolve_session(request,accounts):
    authenticated=accounts.session(request.cookies.get(accounts.cookie_name))
    if authenticated and authenticated.user:return authenticated
    anonymous=accounts.session(request.cookies.get(accounts.guest_cookie_name))
    return anonymous if anonymous and anonymous.user is None else None

def current_session(request:Request,accounts:Annotated[AccountStore,Depends(get_accounts)]):
    session=resolve_session(request,accounts)
    if session is None:raise AccountError(401,'Your session ended. Sign in again.')
    return session

def require_user(session:Annotated[Session,Depends(current_session)]):
    if session.user is None:raise AccountError(401,'Sign in to access this feature.')
    return session.user['id']

def csrf_check(request:Request,accounts:Annotated[AccountStore,Depends(get_accounts)],session:Annotated[Session,Depends(current_session)]):
    origin=request.headers.get('origin')
    token=request.headers.get('x-csrf-token','')
    if origin!=accounts.origin or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token) or not secrets.compare_digest(token,session.csrf):
        raise AccountError(403,'This request could not be verified. Refresh the page and try again.')
    return session

def personal_store(accounts:Annotated[AccountStore,Depends(get_accounts)]):return PersonalStore(accounts)

def cookie(response,accounts,session):
    name=accounts.cookie_name if session.user else accounts.guest_cookie_name
    response.set_cookie(name,session.token,httponly=True,secure=accounts.secure,
        samesite='strict',path='/',max_age=SESSION_SECONDS if session.user else GUEST_SECONDS)
    if session.user:response.delete_cookie(accounts.guest_cookie_name,path='/',secure=accounts.secure,httponly=True,samesite='strict')
    return session.envelope()

@router.get('/api/auth/session',response_model=SessionView)
def session_view(request:Request,response:Response,accounts:Annotated[AccountStore,Depends(get_accounts)]):
    existing=resolve_session(request,accounts)
    # Reads never rewrite an authenticated cookie. A delayed anonymous bootstrap
    # uses a separate cookie and cannot overwrite a newly signed-in session.
    if existing:return existing.envelope()
    return cookie(response,accounts,accounts.bootstrap(None))

@router.post('/api/auth/register',response_model=VerificationReceipt,status_code=201)
def register(body:Registration,request:Request,accounts:Annotated[AccountStore,Depends(get_accounts)],
             previous:Annotated[Session,Depends(csrf_check)]):
    accounts.limit_attempt(request.client.host if request.client else 'unknown',body.username)
    return accounts.register(body.username,body.password,previous.token,body.email)

@router.post('/api/auth/resend-verification',response_model=VerificationReceipt)
def resend_verification(body:Credentials,request:Request,accounts:Annotated[AccountStore,Depends(get_accounts)],
                        previous:Annotated[Session,Depends(csrf_check)]):
    accounts.limit_attempt(request.client.host if request.client else 'unknown',body.username)
    return accounts.resend(body.username,body.password)

@router.post('/api/auth/verify-email',response_model=VerifiedView)
def verify_email(body:VerificationRequest,request:Request,accounts:Annotated[AccountStore,Depends(get_accounts)],
                 previous:Annotated[Session,Depends(csrf_check)]):
    accounts.limit_attempt(request.client.host if request.client else 'unknown','email-verification')
    return accounts.verify_email(body.token)

@router.post('/api/auth/login',response_model=SessionView)
def login(body:Credentials,request:Request,response:Response,accounts:Annotated[AccountStore,Depends(get_accounts)],
          previous:Annotated[Session,Depends(csrf_check)]):
    accounts.limit_attempt(request.client.host if request.client else 'unknown',body.username)
    return cookie(response,accounts,accounts.login(body.username,body.password,previous.token))

@router.post('/api/auth/logout',response_model=SessionView)
def logout(body:LogoutRequest,response:Response,accounts:Annotated[AccountStore,Depends(get_accounts)],
           previous:Annotated[Session,Depends(csrf_check)]):
    accounts.revoke(previous.token)
    response.delete_cookie(accounts.cookie_name,path='/',secure=accounts.secure,httponly=True,samesite='strict')
    return cookie(response,accounts,accounts.bootstrap(None))

@router.get('/api/me/collection',response_model=PersonalView)
def load_collection(owner:Annotated[str,Depends(require_user)],store:Annotated[PersonalStore,Depends(personal_store)]):return {'owner_id':owner,'snapshot':store.load(owner)}

@router.put('/api/me/collection',response_model=PersonalView,dependencies=[Depends(csrf_check)])
def replace_collection(body:PersonalSnapshot,owner:Annotated[str,Depends(require_user)],store:Annotated[PersonalStore,Depends(personal_store)]):return {'owner_id':owner,'snapshot':store.replace(owner,body)}

@router.post('/api/me/collection/import',response_model=PersonalView,dependencies=[Depends(csrf_check)])
def import_collection(body:ImportRequest,owner:Annotated[str,Depends(require_user)],store:Annotated[PersonalStore,Depends(personal_store)]):return {'owner_id':owner,'snapshot':store.import_browser(owner,body)}


@router.put('/api/me/preferences', response_model=SessionView)
def update_preferences(body:PreferencesUpdate,
                       accounts:Annotated[AccountStore,Depends(get_accounts)],
                       session:Annotated[Session,Depends(csrf_check)],
                       owner:Annotated[str,Depends(require_user)]):
    save_preferences(accounts,owner,body)
    current=accounts.session(session.token)
    if current is None:raise AccountError(401,'Your session ended. Sign in again.')
    return current.envelope()


def discovery_preferences(request:Request) -> AccountPreferences:
    # Public discovery does not bootstrap cookies. Failed/expired sessions retain
    # guest discovery behavior; account settings are never taken from a client ID.
    accounts=getattr(request.app.state,'accounts',None)
    session=resolve_session(request,accounts) if accounts is not None else None
    return AccountPreferences.model_validate(session.user['preferences']) if session and session.user else AccountPreferences()
