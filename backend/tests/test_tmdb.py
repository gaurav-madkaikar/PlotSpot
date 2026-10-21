import pytest
from pydantic import ValidationError

from movie_companion.tmdb import map_tmdb_details


def test_maps_complete_movie_details():
    # Synthetic data shaped like TMDB's response; not a real movie record.
    payload = {
        "id": 123,
        "title": "Example Film",
        "release_date": "2024-03-15",
        "runtime": 112,
        "original_language": "ko",
        "genres": [
            {"id": 18, "name": "Drama"},
            {"id": 53, "name": "Thriller"},
        ],
        "poster_path": "/example-poster.jpg",
    }

    movie = map_tmdb_details(payload)

    assert movie.id == 123
    assert movie.title == "Example Film"
    assert movie.year == 2024
    assert movie.runtime_minutes == 112
    assert movie.original_language == "ko"
    assert movie.genres == ["Drama", "Thriller"]
    assert movie.poster_path == "/example-poster.jpg"


def test_missing_optional_metadata_stays_unknown():
    movie = map_tmdb_details({"id": 123, "title": "Example Film"})
    assert movie.year is None
    assert movie.runtime_minutes is None
    assert movie.original_language is None
    assert movie.genres == []
    assert movie.poster_path is None


@pytest.mark.parametrize("release_date", [None, "", "   ", "unknown", "2024-02-30"])
def test_unusable_dates_do_not_invent_a_year(release_date):
    movie = map_tmdb_details({"id": 123, "title": "Example Film", "release_date": release_date})
    assert movie.year is None


@pytest.mark.parametrize("runtime", [None, 0])
def test_unknown_runtime_does_not_become_a_fake_duration(runtime):
    movie = map_tmdb_details({"id": 123, "title": "Example Film", "runtime": runtime})
    assert movie.runtime_minutes is None


def test_empty_optional_fields_are_normalized():
    movie = map_tmdb_details({
        "id": 123,
        "title": "Example Film",
        "genres": [],
        "original_language": "",
        "poster_path": "",
    })
    assert movie.genres == []
    assert movie.original_language is None
    assert movie.poster_path is None


@pytest.mark.parametrize("movie_id", [0, -1, "invalid"])
def test_invalid_movie_identity_is_rejected(movie_id):
    with pytest.raises(ValidationError):
        map_tmdb_details({"id": movie_id, "title": "Example Film"})


@pytest.mark.parametrize("field", ["id", "title"])
def test_missing_required_identity_is_rejected(field):
    payload = {"id": 123, "title": "Example Film"}
    del payload[field]
    with pytest.raises(KeyError):
        map_tmdb_details(payload)


def test_invalid_negative_runtime_is_rejected():
    with pytest.raises(ValidationError):
        map_tmdb_details({"id": 123, "title": "Example Film", "runtime": -10})
