"""TMDB boundary: external responses are translated before reaching the app."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TmdbMovieDetails(BaseModel):
    """Normalized provider data; missing metadata stays unknown."""

    id: int = Field(gt=0)
    title: str
    year: int | None = Field(default=None, ge=1888, le=2100)
    runtime_minutes: int | None = Field(default=None, gt=0)
    original_language: str | None = None
    genres: list[str]
    poster_path: str | None = None


def map_tmdb_details(payload: dict[str, Any]) -> TmdbMovieDetails:
    """Translate movie details and preserve unknown optional metadata."""
    release_date = payload.get("release_date")
    year = None
    if isinstance(release_date, str) and release_date.strip():
        try:
            year = date.fromisoformat(release_date.strip()).year
        except ValueError:
            # A malformed upstream date cannot establish a release year.
            pass

    runtime = payload.get("runtime")
    return TmdbMovieDetails(
        id=payload["id"],
        title=payload["title"],
        year=year,
        runtime_minutes=None if runtime == 0 else runtime,
        original_language=payload.get("original_language") or None,
        genres=[genre["name"] for genre in (payload.get("genres") or [])],
        poster_path=payload.get("poster_path") or None,
    )
