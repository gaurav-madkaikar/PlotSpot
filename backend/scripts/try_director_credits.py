"""Small deterministic pairing exercise; no token, network or LLM needed."""
from movie_companion.name_discovery import director_movie_ids


if __name__ == "__main__":
    crew = [
        {"id": 101, "title": "First film", "job": "Director", "adult": False},
        {"id": 202, "title": "Second film", "job": "Producer", "adult": False},
        {"id": 303, "title": "Third film", "job": "Director", "adult": False},
        {"id": 101, "title": "First film", "job": "Director", "adult": False},
        {"id": 404, "title": "Fourth film", "job": "Writer", "adult": False},
        {"id": 606, "title": "Camera work", "job": "Director of Photography", "adult": False},
        {"id": 505, "title": "Adult film", "job": "Director", "adult": True},
    ]
    ids = director_movie_ids(crew)
    assert ids == [101, 303, 505], f"Expected [101, 303, 505], received {ids}"
    assert director_movie_ids([]) == []
    print("Director-only selection, adult inclusion, deduplication and empty input passed.")
