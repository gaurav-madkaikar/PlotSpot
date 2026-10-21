from fastapi.testclient import TestClient

from movie_companion.catalog import load_catalog
from movie_companion.main import app
from movie_companion.catalog_store import CatalogStore
from movie_companion.settings import get_settings
from movie_companion.search_suggestions import SuggestionIndex, get_suggestion_index
from movie_companion.search_text import normalize_search_text


def test_typo_suggestions_are_backed_by_known_movies_and_actor_appearances():
    index = SuggestionIndex(load_catalog())
    title = index.suggest("Intersteler").items[0]
    assert (title.label, title.kind, title.movie_ids) == ("Interstellar", "movie", [157336])
    actor = index.suggest("Amy Admas").items[0]
    assert actor.label == "Amy Adams" and actor.kind == "actor"
    assert 329865 in actor.movie_ids


def test_exact_fragments_and_unrelated_queries_are_not_corrected():
    index = SuggestionIndex(load_catalog())
    for query in ["Arrival", "amy", "Amy Adams", "   ", "restaurants near me", "zzzzzzzz"]:
        assert index.suggest(query).items == []


def test_index_learns_records_and_evicts_oldest_movies():
    movies = load_catalog()
    index = SuggestionIndex(movies[:2], capacity=2)
    index.remember(movies[2])
    assert list(index.movies) == [movies[1].id, movies[2].id]
    assert index.suggest("Incepton").items == []
    index.remember(movies[1])
    assert list(index.movies)[-1] == movies[1].id


def test_suggestion_route_and_input_bound():
    with TestClient(app) as client:
        data = client.get("/api/search/suggestions", params={"q": "Intersteler"}).json()
        assert data["items"][0]["label"] == "Interstellar"
        assert data["limited"] and data["indexed_movies"] == 10
        assert client.get("/api/search/suggestions", params={"q": "x" * 121}).status_code == 422


def test_normalization_is_idempotent():
    for text in ["Spider-Man: 2021", "  AMY\tADAMS ", "기생충", "---"]:
        normalized = normalize_search_text(text)
        assert normalize_search_text(normalized) == normalized


def test_director_suggestions_have_verified_movie_ids():
    item=SuggestionIndex(load_catalog()).suggest('Cristopher Nolan').items[0]
    assert item.label=='Christopher Nolan' and item.kind=='director'
    assert set(item.movie_ids)=={27205,157336}


def test_localized_aliases_suggest_one_canonical_movie():
    movie=load_catalog()[0].model_copy(update={'title':'Interstellar','alternative_titles':['Interestelar']})
    result=SuggestionIndex([movie]).suggest('Intersteler')
    assert len(result.items)==1 and result.items[0].label=='Interstellar'
    assert result.items[0].movie_ids==[movie.id]


def test_real_title_completion_withholds_unrelated_fuzzy_words():
    template = load_catalog()[0]
    movies = [template.model_copy(update={'id':i, 'title':title, 'cast':[], 'director':None})
              for i, title in enumerate(['Interstellar', 'Interstate', 'Interstelar'], 1)]
    assert [item.label for item in SuggestionIndex(movies).suggest('Interstell').items] == ['Interstellar']


def test_saved_catalog_suggestions_survive_working_cache_eviction(tmp_path, monkeypatch):
    template = load_catalog()[0]
    target = template.model_copy(update={'id': 1, 'title': 'Interstellar', 'source': 'tmdb'})
    movies = [target, *[template.model_copy(update={'id': i, 'title': f'Catalog Record {i}',
              'source': 'tmdb', 'cast': [], 'director': None}) for i in range(2, 1503)]]
    store = CatalogStore(tmp_path / 'movies.db')
    store.import_movies(movies, fetched_at='2026-10-11T10:00:00+00:00')
    index = SuggestionIndex(movies)
    assert target.id not in index.movies
    monkeypatch.setattr(get_settings(), 'data_source', 'tmdb')
    monkeypatch.setattr(app.state, 'catalog_store', store, raising=False)
    monkeypatch.setitem(app.dependency_overrides, get_suggestion_index, lambda: index)
    client = TestClient(app)
    exact = client.get('/api/search/suggestions', params={'q': 'Interstellar'}).json()
    assert exact['items'] == [] and exact['indexed_movies'] == len(movies)
    for query in ['Interstell', 'Intersteler']:
        response = client.get('/api/search/suggestions', params={'q': query})
        assert response.status_code == 200
        assert response.json()['items'][0]['label'] == 'Interstellar'
        assert response.json()['items'][0]['movie_ids'] == [1]
    new = template.model_copy(update={'id': 1503, 'title': 'Newly Discovered', 'source': 'tmdb'})
    store.upsert_movie(new, fetched_at='2026-10-11T10:00:00+00:00')
    assert client.get('/api/search/suggestions', params={'q': 'Newly Discovere'}).json()['items'][0]['label'] == new.title


def test_unavailable_saved_catalog_fails_without_using_incomplete_cache(monkeypatch):
    monkeypatch.setattr(get_settings(), 'data_source', 'tmdb')
    monkeypatch.setattr(app.state, 'catalog_store', None, raising=False)
    assert TestClient(app).get('/api/search/suggestions', params={'q': 'Interstell'}).status_code == 503
