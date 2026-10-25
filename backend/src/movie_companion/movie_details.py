"""Saved metadata first; bounded provider reads and last-good fallback."""
import asyncio
from datetime import datetime, timezone
import sqlite3

from .schemas import Movie
from .tmdb_client import ProviderError


async def load_movie_details(movie_id, *, store, provider) -> Movie:
    try:
        saved = await asyncio.to_thread(store.get_movie, movie_id) if store else None
        presentation_ready = saved and saved.detail_metadata and saved.detail_metadata.presentation_version == 1
        if saved and (presentation_ready or provider is None) and await asyncio.to_thread(store.metadata_is_fresh, movie_id):
            return saved
    except (OSError, sqlite3.Error, ValueError):
        raise ProviderError(503, "Saved movie metadata is unavailable") from None
    if provider is None:
        if saved:
            return saved
        raise ProviderError(503, "Movie metadata is unavailable; configure the movie provider")
    try:
        movie = await provider.movie(movie_id)
    except ProviderError:
        if saved:
            return saved
        raise
    # Provider/client validation is checked again at the persistence boundary.
    if movie.id != movie_id or movie.source != "tmdb":
        raise ProviderError(502, "Movie provider returned mismatched metadata")
    if store:
        try:
            await asyncio.to_thread(store.upsert_movie, movie, fetched_at=datetime.now(timezone.utc).isoformat())
            stored = await asyncio.to_thread(store.get_movie, movie_id)
            if stored is None:
                raise ValueError("Saved movie disappeared")
            return stored
        except (OSError, sqlite3.Error, ValueError):
            raise ProviderError(503, "Movie metadata could not be saved") from None
    return movie
