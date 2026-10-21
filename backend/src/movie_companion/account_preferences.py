"""Explicit account settings; independent of collection revisions and AI memory."""
from pydantic import BaseModel, ConfigDict, Field


class AccountPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(default=0, ge=0, le=9007199254740991)
    allow_spoilers: bool = False
    include_adult: bool = True
    track_movie_history: bool = True


class PreferencesUpdate(AccountPreferences):
    revision: int = Field(ge=0, le=9007199254740991)
    allow_spoilers: bool
    include_adult: bool


PREFERENCES_TABLE = '''CREATE TABLE IF NOT EXISTS account_preferences (
    owner TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    allow_spoilers INTEGER NOT NULL CHECK(allow_spoilers IN (0,1)),
    include_adult INTEGER NOT NULL CHECK(include_adult IN (0,1)),
    track_movie_history INTEGER NOT NULL DEFAULT 1 CHECK(track_movie_history IN (0,1)))'''


def read_preferences(db, owner):
    row = db.execute('SELECT * FROM account_preferences WHERE owner=?', (owner,)).fetchone()
    if row is None:
        return AccountPreferences()
    return AccountPreferences(revision=row['revision'], allow_spoilers=bool(row['allow_spoilers']),
                              include_adult=bool(row['include_adult']), track_movie_history=bool(row['track_movie_history']))


def save_preferences(accounts, owner, incoming):
    from .accounts import AccountError
    with accounts.connect() as db:
        if not db.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone():
            raise AccountError(401, 'Sign in to update your preferences.')
        current = read_preferences(db, owner)
        if current.revision != incoming.revision:
            raise AccountError(409, 'Preferences changed in another tab. Review the latest settings and save again.')
        if current.revision == 9007199254740991:
            raise AccountError(409, 'Preferences cannot be updated. Contact support.')
        updated = incoming.model_copy(update={'revision': current.revision + 1,
            'track_movie_history': incoming.track_movie_history if 'track_movie_history' in incoming.model_fields_set else current.track_movie_history})
        db.execute('''INSERT INTO account_preferences VALUES (?,?,?,?,?)
            ON CONFLICT(owner) DO UPDATE SET revision=excluded.revision,
            allow_spoilers=excluded.allow_spoilers,include_adult=excluded.include_adult,track_movie_history=excluded.track_movie_history''',
            (owner, updated.revision, int(updated.allow_spoilers), int(updated.include_adult), int(updated.track_movie_history)))
        return updated
