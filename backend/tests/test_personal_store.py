import pytest
from movie_companion.accounts import AccountStore,AccountError
from movie_companion.personal_store import PersonalStore
from movie_companion.personal_contracts import PersonalSnapshot,ImportRequest
from test_accounts import PASSWORD,register_verified

def test_isolation_revision_and_atomic_conflict(tmp_path):
    accounts=AccountStore(tmp_path/'private.db');a=register_verified(accounts,'alice',PASSWORD,None).user['id'];b=register_verified(accounts,'bravo',PASSWORD,None).user['id']
    store=PersonalStore(accounts);assert store.load(a).saved==[]
    saved=store.replace(a,PersonalSnapshot(revision=0,saved=[157336],watched=[155],collections=[]))
    assert saved.revision==1 and store.load(b).saved==[]
    with pytest.raises(AccountError) as exc:store.replace(a,PersonalSnapshot(revision=0,saved=[155],watched=[],collections=[]))
    assert exc.value.status==409 and store.load(a)==saved
    assert PersonalStore(AccountStore(accounts.path)).load(a)==saved

def test_explicit_import_merges_names_and_is_membership_idempotent(tmp_path):
    accounts=AccountStore(tmp_path/'private.db');owner=register_verified(accounts,'alice',PASSWORD,None).user['id'];store=PersonalStore(accounts)
    incoming={'revision':0,'saved':[155,157336],'watched':[155],'collections':[{'id':'legacy-id','name':'  Weekend   films ','movieIds':[155]}]}
    first=store.import_browser(owner,ImportRequest.model_validate(incoming))
    assert first.collections[0].name=='Weekend films' and first.collections[0].id!='legacy-id'
    incoming['revision']=first.revision;second=store.import_browser(owner,ImportRequest.model_validate(incoming))
    assert second.saved==first.saved and second.collections==first.collections
    other={**incoming,'revision':second.revision,'saved':[329865],'collections':[{'id':'different','name':'WEEKEND FILMS','movieIds':[329865]}]}
    third=store.import_browser(owner,ImportRequest.model_validate(other))
    assert len(third.collections)==1 and third.collections[0].movieIds==[155,329865]

@pytest.mark.parametrize('change',[{'saved':[1,1]}, {'collections':[{'id':'a'*36,'name':'All saved','movieIds':[]}]},
 {'collections':[{'id':'12345678-1234-1234-1234-123456789abc','name':'Weekend','movieIds':[2]}]}, {'watched':[-1]},{'owner_id':'attacker'}])
def test_contract_rejects_invalid_ownership_and_membership(change):
    with pytest.raises(ValueError):PersonalSnapshot.model_validate({'revision':0,'saved':[1],'watched':[],'collections':[],**change})
