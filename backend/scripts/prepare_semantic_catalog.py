"""Resumable TMDB metadata/embedding preparation; atomic publication at completion."""
import argparse
import asyncio
import hashlib
import math
from pathlib import Path
import shutil
from datetime import datetime, timezone

import httpx

from movie_companion.catalog import load_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.catalog_checkpoint import atomic_json, read_checkpoint
from movie_companion.catalog_import import collect_movies
from movie_companion.embedding_learning import embed_texts
from movie_companion.local_models import verify_local_model
from movie_companion.semantic_catalog import DEFAULT_PATH, MODEL, document_text, read_index, save_index
from movie_companion.settings import get_settings
from movie_companion.tmdb_client import TmdbClient


def text_key(text):
    return hashlib.sha256((MODEL + '\n' + text).encode()).hexdigest()


def valid_vector(vector, dimension):
    return isinstance(vector, list) and len(vector) == dimension and all(not isinstance(n, bool) and isinstance(n, (int, float)) and math.isfinite(n) for n in vector) and any(vector)


async def prepare(args):
    previous = read_index(args.path) if args.path.exists() else None
    if previous and not args.refresh:
        print(f'Retained {len(previous.movies)} films. Use --refresh explicitly; no API/model calls.')
        return
    checkpoint = args.checkpoint or args.path.parent / f'prepare-{args.count}'
    metadata_path = checkpoint / "metadata.json"
    # Resume using the original seed set, even after a successful publication.
    seeds = [m.id for m in previous.movies] if previous else []
    if metadata_path.exists():
        seeds = read_checkpoint(metadata_path).get("config", {}).get("seed_ids", seeds)
    settings = get_settings()
    movies = list(load_catalog())
    if not args.demo:
        if not settings.tmdb_read_token:
            raise ValueError('Configure TMDB_READ_TOKEN locally or explicitly use --demo')
        async with httpx.AsyncClient(base_url='https://api.themoviedb.org/3', timeout=20, follow_redirects=False, headers={'Authorization': f'Bearer {settings.tmdb_read_token}'}) as http:
            movies = await collect_movies(TmdbClient(http), args.count, checkpoint=metadata_path, enrich=True, progress=lambda message: print(message, flush=True), seed_ids=seeds)
    if args.metadata_only:
        if not args.demo and args.path.resolve() == DEFAULT_PATH.resolve():
            CatalogStore().import_movies(movies, fetched_at=datetime.now(timezone.utc).isoformat())
        print(f'Checkpointed {len(movies)} records; embedding/publication deferred.')
        return
    reusable = {text_key(document_text(m)): v for m, v in zip(previous.movies, previous.vectors)} if previous else {}
    vector_path = checkpoint / 'embeddings.json'
    if vector_path.exists():
        saved = read_checkpoint(vector_path)
        if saved.get('model') != MODEL or saved.get('template') != 'metadata-v2':
            raise ValueError('Embedding checkpoint model/template changed')
        if len(saved['vectors']) > 2000 or any(not valid_vector(v, 768) for v in saved['vectors'].values()):
            raise ValueError('Invalid embedding checkpoint')
        reusable.update(saved['vectors'])
    missing = [m for m in movies if text_key(document_text(m)) not in reusable]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False, follow_redirects=False) as ollama:
        await verify_local_model(ollama, MODEL)
        for start in range(0, len(missing), 16):
            batch = missing[start:start + 16]
            vectors = await embed_texts(ollama, model=MODEL, texts=['search_document: ' + document_text(m) for m in batch])
            if not all(valid_vector(v, 768) for v in vectors):
                raise ValueError('Unexpected embedding dimensions')
            reusable.update((text_key(document_text(m)), v) for m, v in zip(batch, vectors))
            atomic_json(vector_path, {'model': MODEL, 'template': 'metadata-v2', 'vectors': reusable})
            print(f'Embedded {min(start + 16, len(missing))}/{len(missing)} changed records.', flush=True)
    # Metadata is usable independently; an index-publication failure does not
    # make these validated records unusable on the detail page.
    if not args.demo and args.path.resolve() == DEFAULT_PATH.resolve():
        CatalogStore().import_movies(movies, fetched_at=datetime.now(timezone.utc).isoformat())
    # Back up the published snapshot only after all new metadata/vectors are ready.
    if previous:
        backup = args.path.with_name('semantic-catalog.previous.json')
        shutil.copy2(args.path, backup)
    saved = save_index(movies, [reusable[text_key(document_text(m))] for m in movies], args.path, source_movie_ids=[m.id for m in movies] if not args.demo else None)
    print(f'Published {len(saved.movies)} {movies[0].source} films; {len(saved.vectors[0])} dimensions; {saved.model}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--metadata-only', action='store_true')
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--count', type=int, default=1500, choices=range(10, 1501), metavar='10..1500')
    asyncio.run(prepare(parser.parse_args()))
