"""Small persistent discovery index, separate from cited discussion evidence."""
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .catalog import load_catalog
from .schemas import Movie

MODEL = "nomic-embed-text:v1.5"
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data/private/semantic-catalog.json"


def document_text(movie: Movie) -> str:
    # Synopsis metadata only: no scripts, ending passages or background news.
    base = f"Title: {movie.title}\nGenres: {', '.join(movie.genres)}\nSynopsis: {movie.overview}\nDirector: {movie.director or ''}\nCast: {', '.join(movie.cast)}"
    if movie.keywords:
        base += f"\nKeywords: {', '.join(movie.keywords[:30])}"
    if movie.alternative_titles:
        base += f"\nAlternative titles: {', '.join(movie.alternative_titles[:8])}"
    return base


def fingerprint(movies: list[Movie], *, version="metadata-v2") -> str:
    payload = json.dumps([m.model_dump(mode="json", exclude={"keywords", "alternative_titles", "adult", "detail_metadata"} if version == "metadata-v1" else ({key for key in ("adult", "detail_metadata") if getattr(m, key) is None})) for m in movies], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((MODEL + "\n" + version + "\n" + payload).encode()).hexdigest()


class CatalogIndex(BaseModel):
    version: Literal["metadata-v1", "metadata-v2"] = "metadata-v2"
    model: Literal["nomic-embed-text:v1.5"] = MODEL
    prepared_at: str
    fingerprint: str
    movies: list[Movie] = Field(min_length=1, max_length=1500)
    vectors: list[list[float]]
    # IDs verified by the explicit TMDB importer; never accepted from a search caller.
    source_movie_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=list, max_length=1500)

    @field_validator("vectors", mode="before")
    @classmethod
    def numeric_vectors(cls, vectors):
        if not isinstance(vectors, list) or not all(isinstance(v, list) for v in vectors):
            raise ValueError("Vectors must be lists")
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) for v in vectors for n in v):
            raise ValueError("Vector coordinates must be numeric")
        return vectors

    @model_validator(mode="after")
    def validate_index(self):
        if self.version == 'metadata-v1' and any(m.keywords or m.alternative_titles or m.adult is not None or m.detail_metadata is not None for m in self.movies):
            raise ValueError('Legacy snapshots cannot carry unhashed new metadata')
        ids = [m.id for m in self.movies]
        allowed = set(self.source_movie_ids) if self.source_movie_ids else {m.id for m in load_catalog()}
        if self.source_movie_ids and (len(allowed) != len(self.source_movie_ids) or allowed != set(ids) or any(m.source != "tmdb" for m in self.movies)):
            raise ValueError("Importer identity manifest must match TMDB records")
        if len(set(ids)) != len(ids) or not set(ids) <= allowed:
            raise ValueError("Catalog IDs must be unique reviewed movie IDs")
        if len(self.vectors) != len(self.movies) or not self.vectors or not self.vectors[0]:
            raise ValueError("Every movie requires an embedding")
        dimension = len(self.vectors[0])
        for vector in self.vectors:
            if len(vector) != dimension or not all(math.isfinite(v) for v in vector) or not any(vector) or not math.isfinite(sum(v * v for v in vector)):
                raise ValueError("Invalid catalog vectors")
        if self.fingerprint != fingerprint(self.movies, version=self.version):
            raise ValueError("Metadata fingerprint mismatch")
        if len({m.source for m in self.movies}) != 1:
            raise ValueError("Catalog metadata must use one provider")
        return self


def read_index(path: Path = DEFAULT_PATH) -> CatalogIndex:
    if path.stat().st_size > 40_000_000:
        raise ValueError("Catalog exceeds storage bound")
    return CatalogIndex.model_validate_json(path.read_text())


def save_index(movies: list[Movie], vectors: list[list[float]], path: Path = DEFAULT_PATH, *, source_movie_ids: list[int] | None = None) -> CatalogIndex:
    index = CatalogIndex(prepared_at=datetime.now(timezone.utc).isoformat(), fingerprint=fingerprint(movies), movies=movies, vectors=vectors, source_movie_ids=source_movie_ids or [])
    serialized = index.model_dump_json()
    if len(serialized.encode()) > 40_000_000:
        raise ValueError('Catalog exceeds storage bound')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Failed preparation never replaces the published index; rename is atomic.
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".catalog-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as file:
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return index
