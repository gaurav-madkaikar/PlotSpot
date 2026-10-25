import json
from functools import lru_cache
from pathlib import Path

from .schemas import Movie


@lru_cache(maxsize=1)
def load_catalog() -> tuple[Movie, ...]:
    """Validate authored fixtures once; a future TMDB adapter can replace this."""
    path = Path(__file__).parent / "data" / "movies.json"
    movies = tuple(Movie.model_validate(record) for record in json.loads(path.read_text()))
    if len({movie.id for movie in movies}) != len(movies):
        raise ValueError("Catalog contains duplicate movie IDs")
    return movies


def search_movies(
    query: str = "", genre: str | None = None, max_runtime: int | None = None, language: str | None = None
) -> list[Movie]:
    needle = query.strip().casefold()
    language_normalized = language.casefold().strip() if language is not None else None
    return [
        movie
        for movie in load_catalog()
        if (not needle or needle in " ".join([movie.title, *movie.cast]).casefold())
        and (not genre or genre.casefold() in {item.casefold() for item in movie.genres})
        and (max_runtime is None or movie.runtime_minutes <= max_runtime)
        and (language_normalized is None or language_normalized == "" or movie.language.casefold().strip() == language_normalized)
    ]


def get_movie(movie_id: int) -> Movie | None:
    return next((movie for movie in load_catalog() if movie.id == movie_id), None)
