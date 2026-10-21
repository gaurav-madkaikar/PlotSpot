"""Feature inventory describes reviewed sources/publications, not live service health."""
from pydantic import BaseModel

from .wikipedia_source import MOVIE_ARTICLES


class MovieFeatures(BaseModel):
    movie_id: int
    discussion: bool
    quiz: bool
    facts: bool


def movie_features(movie_id, store):
    saved = store.load(movie_id)
    return MovieFeatures(movie_id=movie_id, discussion=movie_id in MOVIE_ARTICLES,
                         quiz=saved is not None, facts=saved is not None)
