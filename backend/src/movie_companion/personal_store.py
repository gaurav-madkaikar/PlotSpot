"""Owner-scoped personal state with atomic version checks and explicit import."""
import json
from uuid import uuid4
from pydantic import ValidationError
from .accounts import AccountError
from .personal_contracts import PersonalSnapshot,PersonalCollection,name_key

class PersonalStore:
    def __init__(self,accounts):
        self.accounts=accounts
        with accounts.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS personal_collections (owner TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, revision INTEGER NOT NULL, payload TEXT NOT NULL)')

    def _load(self,db,owner):
        if not db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise AccountError(401,'Sign in to use your account collection.')
        row=db.execute('SELECT revision,payload FROM personal_collections WHERE owner=?',(owner,)).fetchone()
        if row is None:return PersonalSnapshot(revision=0,saved=[],watched=[],collections=[])
        return PersonalSnapshot.model_validate({'revision':row['revision'],**json.loads(row['payload'])})

    def load(self,owner):
        with self.accounts.connect() as db:return self._load(db,owner)

    def _replace(self,db,owner,snapshot):
        current=self._load(db,owner)
        if current.revision!=snapshot.revision:raise AccountError(409,'Your collection changed in another tab. Review the latest version and try again.')
        updated=PersonalSnapshot.model_validate({**snapshot.model_dump(),'revision':current.revision+1})
        payload=json.dumps(updated.model_dump(exclude={'revision'}),ensure_ascii=False)
        db.execute('INSERT INTO personal_collections VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(owner,updated.revision,payload))
        return updated

    def replace(self,owner,snapshot):
        snapshot=PersonalSnapshot.model_validate(snapshot.model_dump())
        with self.accounts.connect() as db:return self._replace(db,owner,snapshot)

    def import_browser(self,owner,incoming):
        with self.accounts.connect() as db:
            current=self._load(db,owner)
            if current.revision!=incoming.revision:raise AccountError(409,'Your collection changed in another tab. Review the latest version and try again.')
            by_name={name_key(c.name):c.model_copy(deep=True) for c in current.collections}
            for c in incoming.collections:
                key=name_key(c.name)
                if key in by_name:by_name[key].movieIds=list(dict.fromkeys([*by_name[key].movieIds,*c.movieIds]))
                else:by_name[key]=PersonalCollection(id=str(uuid4()),name=c.name,movieIds=c.movieIds)
            try:
                merged=PersonalSnapshot(revision=current.revision,saved=list(dict.fromkeys([*current.saved,*incoming.saved])),
                    watched=list(dict.fromkeys([*current.watched,*incoming.watched])),collections=list(by_name.values()))
            except ValidationError as error:
                raise AccountError(422,'The combined collection exceeds the account limits. Import fewer films or collections.') from error
            return self._replace(db,owner,merged)
