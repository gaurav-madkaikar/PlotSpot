"""Run after completing get_movie; no API or LLM needed."""
from movie_companion.catalog_store import CatalogStore


if __name__ == "__main__":
    store = CatalogStore()
    movie = store.get_movie(157336)
    assert movie is not None and movie.title == "Interstellar"
    print(movie.title, movie.year, movie.director)
    assert store.get_movie(999999999) is None
    # A new instance reads the same persistent file.
    assert CatalogStore().get_movie(157336) == movie
    print("Existing movie, missing movie and reopened database checks passed.")
