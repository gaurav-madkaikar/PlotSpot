import pytest
from fastapi.testclient import TestClient

from movie_companion.main import app

client = TestClient(app)


def test_catalog_is_truthful_and_uses_unique_ids():
    response = client.get("/api/search")
    assert response.status_code == 200
    data = response.json()
    assert data["data_source"] == "demo"
    assert data["total"] == len(data["items"]) == 10
    assert len({movie["id"] for movie in data["items"]}) == 10
    assert all(movie["artwork_kind"] == "illustration" for movie in data["items"])


def test_actor_search_and_combined_constraints():
    response = client.get(
        "/api/search", params={"q": "  AMY ADAMS  ", "genre": "science fiction", "max_runtime": 120}
    )
    assert [movie["title"] for movie in response.json()["items"]] == ["Arrival"]
    assert client.get("/api/search", params={"q": "Amy Adams", "max_runtime": 100}).json()["total"] == 0


def test_unknown_query_and_whitespace_query():
    assert client.get("/api/search", params={"q": "nonexistent film"}).json()["items"] == []
    assert client.get("/api/search", params={"q": "   "}).json()["total"] == 10


@pytest.mark.parametrize("params", [{"q": "x" * 121}, {"max_runtime": -1}, {"max_runtime": "abc"}])
def test_invalid_search_requests_are_rejected(params):
    assert client.get("/api/search", params=params).status_code == 422


def test_movie_routes_do_not_invent_records():
    assert client.get("/api/movies/157336").json()["title"] == "Interstellar"
    assert client.get("/api/movies/999999999").status_code == 404
    assert client.get("/api/movies/not-a-number").status_code == 422

# Test the movie search functionality with specific genre and runtime constraints
def test_movie_search_functionality():
    response = client.get("/api/search", params={"genre": "Drama", "max_runtime": 120})
    assert response.status_code == 200
    data = response.json()
    print(f"Response data: {data}")
    assert "items" in data and isinstance(data["items"], list) and len(data["items"]) == 2
    assert all("Drama" in movie["genres"] for movie in data["items"])
    assert all(movie["runtime_minutes"] <= 120 for movie in data["items"])
    assert sorted(movie["title"] for movie in data["items"]) == ["Arrival", "The Truman Show"]

def test_movie_search_with_language():
    response = client.get("/api/search", params={"language": "Korean"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["title"] == "Parasite"

    response = client.get("/api/search", params={"language": "japanese"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["title"] == "Spirited Away"

    response = client.get("/api/search", params={"language": "Korean", "max_runtime": 120})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = client.get("/api/search", params={})
    assert response.status_code == 200
    print(f"search data: {response.json()}")
    assert len(response.json()["items"]) == 10

    response = client.get("/api/search", params={"language": " "})
    assert response.status_code == 200
    print(f"search data: {response.json()}")
    assert len(response.json()["items"]) == 10
