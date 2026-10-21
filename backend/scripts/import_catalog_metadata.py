"""Copy validated saved catalog metadata to SQLite; no network or model calls."""
from movie_companion.catalog_store import CatalogStore
from movie_companion.semantic_catalog import read_index


if __name__ == "__main__":
    index = read_index()
    store = CatalogStore()
    # The original preparation date is not replaced with today's import date.
    store.import_movies(index.movies, fetched_at=index.prepared_at)
    print(f"Imported {len(index.movies)} movie records into {store.path}")
