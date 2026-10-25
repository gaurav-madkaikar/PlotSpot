"""Bounded genre-balanced TMDB preparation with resumable metadata checkpoints."""
import asyncio
from datetime import date
from pathlib import Path

from .catalog import load_catalog
from .catalog_checkpoint import atomic_json, read_checkpoint
from .schemas import Movie
from .tmdb_client import ProviderError, TmdbClient


def record_ids(records):
    ids = []
    for record in records:
        movie_id = record.get('id')
        if not isinstance(movie_id, int) or isinstance(movie_id, bool) or movie_id <= 0:
            raise ValueError('Invalid provider movie ID')
        if movie_id not in ids:
            ids.append(movie_id)
    return ids


async def retry_read(call, *, attempts=3):
    """Bound retries for transient provider failures; never retry missing films."""
    for attempt in range(attempts):
        try:
            return await call()
        except ProviderError as error:
            if error.status not in {502, 503, 504} or attempt == attempts - 1:
                raise
            await asyncio.sleep(2 ** attempt)


async def collect_movies(provider: TmdbClient, count: int = 200, *, checkpoint: Path | None = None, enrich=False, progress=None, seed_ids=None):
    if not 10 <= count <= 1500:
        raise ValueError('Catalog size must be between 10 and 1500')
    payload = await retry_read(lambda: provider._get('/genre/movie/list'))
    genres = provider._records(payload, 'genres')
    genre_ids = [g.get('id') for g in genres]
    if not genre_ids or len(genre_ids) > 30 or any(not isinstance(g, int) or isinstance(g, bool) or g <= 0 for g in genre_ids):
        raise ValueError('Invalid provider genre list')
    as_of = date.today().isoformat()
    config = {'version': 'import-v2', 'count': count, 'enrich': enrich, 'genre_ids': genre_ids, 'as_of': as_of, 'seed_ids': seed_ids or []}
    saved = read_checkpoint(checkpoint) if checkpoint and checkpoint.exists() else None
    if saved and saved.get('config') != config:
        raise ValueError('Checkpoint configuration changed; choose a new checkpoint path')
    ids = saved['ids'] if saved else list(dict.fromkeys([m.id for m in load_catalog()] + (seed_ids or [])))
    if len(ids) > 2000 or record_ids([{'id': mid} for mid in ids]) != ids:
        raise ValueError('Invalid checkpoint identities')
    completed = {}
    if saved:
        for key, value in saved['movies'].items():
            movie = Movie.model_validate(value)
            if str(movie.id) != key or movie.id not in ids or movie.source != 'tmdb':
                raise ValueError('Invalid checkpoint movie')
            completed[movie.id] = movie
    if len(completed) > 2000:
        raise ValueError('Metadata checkpoint exceeds bound')
    page_start = saved.get('next_page', 1) if saved else 1
    def persist(next_page):
        if checkpoint:
            atomic_json(checkpoint, {'config': config, 'ids': ids, 'next_page': next_page, 'movies': {str(mid): m.model_dump(mode='json') for mid, m in completed.items()}})
    pool_target = min(2000, count + max(60, count // 5))
    next_page = page_start
    for page in range(page_start, 31):
        if len(ids) >= pool_target:
            break
        async def group(genre_id):
            payload = await retry_read(lambda: provider._get('/discover/movie', include_adult='true', include_video='false', with_genres=genre_id, page=page, sort_by='vote_average.desc', **{'vote_count.gte': 100, 'primary_release_date.lte': as_of}))
            return record_ids(provider._records(payload, 'results'))
        groups = await asyncio.gather(*(group(g) for g in genre_ids))
        before = len(ids)
        for i in range(max((len(group) for group in groups), default=0)):
            for group_ids in groups:
                if i < len(group_ids) and group_ids[i] not in ids:
                    ids.append(group_ids[i])
                if len(ids) >= pool_target:
                    break
            if len(ids) >= pool_target:
                break
        next_page = page + 1
        persist(next_page)
        if progress:
            progress(f'Collected {len(ids)} candidate IDs (page {page}).')
        if len(ids) == before:
            break
    if len(ids) < count:
        raise ValueError('Not enough provider IDs; existing catalog retained')
    await retry_read(lambda: provider._get('/configuration/languages'))
    # Fetch only unfinished metadata; provider limits requests to four at a time.
    if len(completed) >= count:
        return [completed[mid] for mid in ids if mid in completed][:count]
    for start in range(0, len(ids), 8):
        batch = [mid for mid in ids[start:start + 8] if mid not in completed]
        async def fetch(mid):
            call = (lambda: provider.movie(mid, enrich=True)) if enrich else (lambda: provider.movie(mid))
            return await retry_read(call)
        outcomes = await asyncio.gather(*(fetch(mid) for mid in batch), return_exceptions=True)
        failure = None
        for mid, outcome in zip(batch, outcomes):
            if isinstance(outcome, ProviderError) and outcome.status == 404:
                continue
            if isinstance(outcome, Exception):
                failure = outcome
                continue
            if outcome.id != mid or outcome.source != 'tmdb':
                failure = ValueError('Provider movie identity mismatch')
                continue
            if outcome.title.strip() and outcome.overview.strip():
                completed[mid] = outcome.model_copy(update={'cast': outcome.cast[:6]})
        persist(next_page)
        if progress:
            progress(f'Prepared {len(completed)}/{count} movie records.')
        if failure:
            raise ProviderError(502, 'Catalog fetch failed; resume from checkpoint') from None
        if len(completed) >= count:
            return [completed[mid] for mid in ids if mid in completed][:count]
    raise ValueError('Not enough complete records; existing catalog retained')
