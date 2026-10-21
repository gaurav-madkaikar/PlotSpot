"""Translate lightweight provider records without inventing omitted full metadata."""
import re

from .schemas import Movie
from .tmdb import map_tmdb_details


def map_movie_preview(payload, movie_id, languages):
    mapped = map_tmdb_details(payload)
    if mapped.id != movie_id:
        raise ValueError('Movie preview identity mismatch')
    names = {item['iso_639_1']: item['english_name'] for item in languages}
    poster = mapped.poster_path
    if poster and not re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', poster):
        poster = None
    original = payload.get('original_title')
    return Movie(id=mapped.id, title=mapped.title, year=mapped.year,
        runtime_minutes=mapped.runtime_minutes, language=names.get(mapped.original_language, mapped.original_language or 'Unknown'),
        genres=mapped.genres, overview=payload.get('overview') or '', tagline='', cast=[], director=None,
        vote_average=payload.get('vote_average'), vote_count=payload.get('vote_count'),
        adult=payload.get('adult'), alternative_titles=[original] if isinstance(original, str) and original.strip() and original != mapped.title and len(original) <= 200 else [],
        cover_url=f'https://image.tmdb.org/t/p/w500{poster}' if poster else None,
        source='tmdb', artwork_kind='poster' if poster else 'placeholder')
