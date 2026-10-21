"""Fetch/cache a reviewed script, index scenes locally, optionally inspect retrieval."""
import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.evidence_store import EvidenceStore
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.screenplay_retrieval import MODEL, index_script, retrieve_script
from movie_companion.screenplay_source import SCRIPTS, load_script, scene_sections

BACKEND = Path(__file__).resolve().parents[1]


async def main(args):
    if args.query and not args.allow_spoilers:
        raise ValueError('Use --allow-spoilers to retrieve screenplay content')
    if args.report:
        if args.report.suffix != '.json' or args.report.resolve().is_relative_to(args.cache_root.resolve()):
            raise ValueError('Choose a JSON report outside the source cache')
    started = monotonic()
    async with asyncio.timeout(args.deadline_seconds):
        async with httpx.AsyncClient(base_url='https://imsdb.com', timeout=40, trust_env=False,
                                    follow_redirects=False) as source_client:
            snapshot, state = await load_script(source_client, movie_id=args.movie_id,
                                                cache_root=args.cache_root, refresh=args.refresh)
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                    trust_env=False, follow_redirects=False) as model_client:
            await verify_local_model(model_client, MODEL)
            store = await asyncio.to_thread(EvidenceStore, args.evidence_store)
            counts = await index_script(model_client, snapshot=snapshot, store=store)
            hits = await retrieve_script(model_client, snapshot=snapshot, store=store,
                                        query=args.query, allow_spoilers=args.allow_spoilers) if args.query else []
    report = {'movie_id': snapshot.movie_id, 'source_ref': snapshot.source_ref,
              'version': SCRIPTS[snapshot.movie_id].version_label, 'revision': snapshot.revision,
              'source_cache': state, 'text_characters': len(snapshot.text),
              'scenes_including_opening': len(scene_sections(snapshot.text)), 'index': counts,
              'embedding_model': MODEL, 'embedding_digest': DIGESTS[MODEL],
              'query': args.query, 'hits': [{key: value for key, value in asdict(h).items() if key != 'text'} for h in hits],
              'eligible_for_scored_quiz': snapshot.eligible_for_quiz,
              'elapsed_seconds': round(monotonic()-started, 2)}
    if args.report:
        atomic_json(args.report, report)
    print(f"{SCRIPTS[snapshot.movie_id].title}: source {state}, {counts['chunks']} chunks; "
          f"{counts['indexed_documents']} indexed, {counts['cached_documents']} cached documents.")
    for hit in hits:
        print(f'{hit.score:.3f} · {hit.scene} · characters {hit.start}:{hit.end}')
    print('Script retrieval ready; released-film quiz verification still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie-id', type=int, choices=sorted(SCRIPTS), required=True)
    parser.add_argument('--query')
    parser.add_argument('--allow-spoilers', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--cache-root', type=Path, default=BACKEND/'data/private/screenplays')
    parser.add_argument('--evidence-store', type=Path, default=BACKEND/'data/content-evidence')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--deadline-seconds', type=int, choices=range(1, 601), default=300)
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, TypeError, UnicodeError, httpx.HTTPError, TimeoutError, OSError) as error:
        raise SystemExit(f'Screenplay ingestion failed ({type(error).__name__}): {error}') from error
