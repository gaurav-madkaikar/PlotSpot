"""Durable movie metadata; independent of discovery vectors and generated content."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .schemas import Movie

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data/private/movie-catalog.db"


class CatalogStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported catalog database version")
            db.execute("CREATE TABLE IF NOT EXISTS movies (movie_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, fetched_at TEXT NOT NULL)")
            db.execute("PRAGMA user_version = 1")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _validated(movie):
        movie = Movie.model_validate(movie.model_dump())
        if movie.source != "tmdb" or not movie.title.strip():
            raise ValueError("Catalog requires named TMDB movies")
        return movie

    def import_movies(self, movies: list[Movie], *, fetched_at: str, preview: bool = False) -> None:
        timestamp = datetime.fromisoformat(fetched_at)
        if timestamp.tzinfo is None:
            raise ValueError("Metadata timestamp must include its timezone")
        validated = [self._validated(movie) for movie in movies]
        if len({m.id for m in validated}) != len(validated):
            raise ValueError("Duplicate movie IDs in import")
        with self._connect() as db:
            for movie in validated:
                old = db.execute("SELECT payload, fetched_at FROM movies WHERE movie_id = ?", (movie.id,)).fetchone()
                incoming = movie.model_dump()
                if old:
                    previous = Movie.model_validate_json(old["payload"])
                    if previous.id != movie.id:
                        raise ValueError("Stored movie identity mismatch")
                    if preview and previous.detail_metadata is not None:
                        continue  # A tile refresh cannot make older full details fresh.
                    if datetime.fromisoformat(old["fetched_at"]) > timestamp:
                        continue  # Older snapshots cannot overwrite fresher metadata.
                    if movie.detail_metadata is not None and previous.detail_metadata is not None:
                        richer = previous.detail_metadata.model_dump()
                        metadata = movie.detail_metadata.model_dump()
                        for key, value in richer.items():
                            if metadata[key] in (None, "", []) and value not in (None, "", []):
                                metadata[key] = value
                        incoming["detail_metadata"] = metadata
                    for field, value in previous.model_dump().items():
                        if incoming[field] in (None, "", []) and value not in (None, "", []):
                            incoming[field] = value
                    if movie.cover_url is None and previous.cover_url:
                        incoming["artwork_kind"] = previous.artwork_kind
                merged = self._validated(Movie.model_validate(incoming))
                db.execute("INSERT INTO movies (movie_id, payload, fetched_at) VALUES (?, ?, ?) ON CONFLICT(movie_id) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at", (merged.id, merged.model_dump_json(), fetched_at))

    def upsert_movie(self, movie: Movie, *, fetched_at: str) -> None:
        self.import_movies([movie], fetched_at=fetched_at)

    def get_movie(self, movie_id: int) -> Movie | None:
        """Learner-written lookup, validated before returning to the API."""
        if type(movie_id) is not int or movie_id <= 0:
            raise ValueError("Movie ID must be a positive integer")
        with self._connect() as db:
            result = db.execute(
                "SELECT payload FROM movies WHERE movie_id = ?",
                (movie_id,),
            ).fetchone()
            if result is None:
                return None
            movie = self._validated(Movie.model_validate_json(result["payload"]))
            if movie.id != movie_id:
                raise ValueError("Stored movie identity mismatch")
            return movie

    def metadata_is_fresh(self, movie_id: int, *, now=None) -> bool:
        now = now or datetime.now(timezone.utc)
        with self._connect() as db:
            row = db.execute("SELECT fetched_at FROM movies WHERE movie_id = ?", (movie_id,)).fetchone()
        if row is None:
            return False
        try:
            fetched = datetime.fromisoformat(row["fetched_at"])
            return fetched.tzinfo is not None and timedelta(0) <= now - fetched < timedelta(days=7)
        except (ValueError, TypeError):
            return False

    def identity_movies(self) -> list[Movie]:
        """Metadata candidates only; this does not publish semantic vectors."""
        with self._connect() as db:
            rows = db.execute("SELECT movie_id, payload FROM movies ORDER BY movie_id").fetchall()
        movies = []
        for row in rows:
            movie = self._validated(Movie.model_validate_json(row["payload"]))
            if movie.id != row["movie_id"]:
                raise ValueError("Stored movie identity mismatch")
            movies.append(movie)
        return movies

    def search_revision(self):
        """Observe writes from this or another process, including SQLite WAL writes."""
        revision = []
        for path in (self.path, Path(str(self.path) + '-wal')):
            try:
                stat = path.stat()
                revision.append((stat.st_mtime_ns, stat.st_size))
            except FileNotFoundError:
                revision.append(None)
        return tuple(revision)
