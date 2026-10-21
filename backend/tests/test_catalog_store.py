import sqlite3

import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.schemas import Movie

STAMP = "2026-10-10T10:00:00+00:00"


def movie():
    return load_catalog()[0].model_copy(update={"source": "tmdb"})


def read_row(path, movie_id):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT payload, fetched_at FROM movies WHERE movie_id = ?", (movie_id,)).fetchone()


def test_import_survives_reopen_and_is_idempotent(tmp_path):
    path = tmp_path / "catalog.db"
    CatalogStore(path).import_movies([movie()], fetched_at=STAMP)
    CatalogStore(path).import_movies([movie()], fetched_at=STAMP)
    assert Movie.model_validate_json(read_row(path, movie().id)[0]) == movie()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM movies").fetchone()[0] == 1


def test_partial_update_preserves_richer_fields_and_older_snapshot_cannot_overwrite(tmp_path):
    path = tmp_path / "catalog.db"
    store = CatalogStore(path)
    rich = movie().model_copy(update={"keywords": ["dream"], "director": "Existing director"})
    store.upsert_movie(rich, fetched_at=STAMP)
    sparse = rich.model_copy(update={"cast": [], "keywords": [], "director": None})
    store.upsert_movie(sparse, fetched_at="2026-10-11T10:00:00+00:00")
    assert Movie.model_validate_json(read_row(path, rich.id)[0]).cast == rich.cast
    store.upsert_movie(rich.model_copy(update={"title": "Old title"}), fetched_at=STAMP)
    saved, timestamp = read_row(path, rich.id)
    assert Movie.model_validate_json(saved).title == rich.title
    assert timestamp == "2026-10-11T10:00:00+00:00"


def test_invalid_batch_does_not_partially_publish(tmp_path):
    path = tmp_path / "catalog.db"
    store = CatalogStore(path)
    invalid = movie().model_copy(update={"id": 0})
    with pytest.raises(ValueError):
        store.import_movies([movie(), invalid], fetched_at=STAMP)
    assert read_row(path, movie().id) is None
    with pytest.raises(ValueError, match="Duplicate"):
        store.import_movies([movie(), movie()], fetched_at=STAMP)


def test_corrupt_stored_identity_rolls_back_entire_update(tmp_path):
    path = tmp_path / "catalog.db"
    store = CatalogStore(path)
    a = movie()
    b = a.model_copy(update={"id": a.id + 1})
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO movies VALUES (?, ?, ?)", (b.id, a.model_dump_json(), STAMP))
    with pytest.raises(ValueError, match="identity"):
        store.import_movies([a, b], fetched_at=STAMP)
    assert read_row(path, a.id) is None


def test_timezone_and_source_are_required(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    with pytest.raises(ValueError, match="timezone"):
        store.upsert_movie(movie(), fetched_at="2026-10-10T10:00:00")
    with pytest.raises(ValueError, match="TMDB"):
        store.upsert_movie(load_catalog()[0], fetched_at=STAMP)


def test_lookup_returns_validated_movie_and_none_and_survives_restart(tmp_path):
    path = tmp_path / "catalog.db"
    CatalogStore(path).upsert_movie(movie(), fetched_at=STAMP)
    assert CatalogStore(path).get_movie(movie().id) == movie()
    assert CatalogStore(path).get_movie(999999999) is None


@pytest.mark.parametrize("movie_id", [0, -1, True, "1 OR 1=1"])
def test_lookup_rejects_invalid_identity(tmp_path, movie_id):
    with pytest.raises(ValueError, match="positive integer"):
        CatalogStore(tmp_path / "catalog.db").get_movie(movie_id)


def test_lookup_rejects_corrupt_payload_and_mismatched_identity(tmp_path):
    path = tmp_path / "catalog.db"
    store = CatalogStore(path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO movies VALUES (?, ?, ?)", (123, movie().model_dump_json(), STAMP))
        db.execute("INSERT INTO movies VALUES (?, ?, ?)", (456, '{"title": "incomplete"}', STAMP))
    with pytest.raises(ValueError, match="identity"):
        store.get_movie(123)
    with pytest.raises(ValueError):
        store.get_movie(456)


def test_freshness_boundary_and_future_timestamp(tmp_path):
    from datetime import datetime, timezone
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_movie(movie(), fetched_at=STAMP)
    assert store.metadata_is_fresh(movie().id, now=datetime(2026, 10, 16, 10, tzinfo=timezone.utc))
    assert not store.metadata_is_fresh(movie().id, now=datetime(2026, 10, 17, 10, tzinfo=timezone.utc))
    assert not store.metadata_is_fresh(movie().id, now=datetime(2026, 10, 9, tzinfo=timezone.utc))
