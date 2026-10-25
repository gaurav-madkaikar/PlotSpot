import pytest

from movie_companion.settings import get_settings
from movie_companion.search_suggestions import get_suggestion_index


@pytest.fixture(autouse=True)
def offline_settings(monkeypatch):
    """A developer's local credential must never turn tests into live requests."""
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "demo")
    monkeypatch.setenv("TMDB_READ_TOKEN", "")
    get_settings.cache_clear()
    get_suggestion_index.cache_clear()
    yield
    get_settings.cache_clear()
    get_suggestion_index.cache_clear()


@pytest.fixture
def content_member(tmp_path, monkeypatch):
    """Opt-in real cookie/CSRF session for content HTTP contract tests only."""
    from fastapi.testclient import TestClient
    from movie_companion.accounts import AccountStore
    from movie_companion.account_routes import get_accounts
    from movie_companion.main import app
    from test_accounts import register_verified, PASSWORD
    monkeypatch.setenv('FRAME_ACCOUNT_DB', str(tmp_path/'lifespan-accounts.db'))
    store=AccountStore(tmp_path/'member-accounts.db')
    signed=register_verified(store,'ContentViewer',PASSWORD,None)
    app.dependency_overrides[get_accounts]=lambda:store
    def client():
        result=TestClient(app,headers={'Origin':store.origin,'X-CSRF-Token':signed.csrf})
        result.cookies.set(store.cookie_name,signed.token)
        return result
    yield client
    app.dependency_overrides.pop(get_accounts,None)
