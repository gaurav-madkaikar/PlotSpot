"""Inspect local-model background facts, or explicitly publish inspected selection."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from movie_companion.background_articles import DEFAULT_CACHE, get_article
from movie_companion.background_registry import articles_for_movie
from movie_companion.background_fact_workflow import inspect_facts, publish_reviewed
from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.evidence_store import EvidenceStore


async def prepare(args):
    store = ContentStore(args.database)
    if args.selection:
        result = publish_reviewed(store, report_path=args.report, selection_path=args.selection, cache_dir=args.cache)
        print(json.dumps(result))
        return
    saved = store.load(args.movie_id)
    if saved is None:
        raise ValueError('A saved movie collection is required')
    records = articles_for_movie(args.movie_id)

    async def fetch(record):
        url = urlsplit(record.url)
        async with httpx.AsyncClient(base_url=f'{url.scheme}://{url.netloc}', timeout=25,
                trust_env=False, follow_redirects=False,
                headers={'User-Agent':'MovieCompanionLearning/0.1 (local educational reader)'}) as client:
            return await get_article(client, identifier=record.id, refresh=args.refresh, cache_dir=args.cache)
    # Independent read-only sources; failure cancels/joins the other fetch before exiting.
    async with asyncio.timeout(55):
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(fetch(record)) for record in records]
    articles = [task.result() for task in tasks]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=90,
                               trust_env=False, follow_redirects=False) as model:
        report = await inspect_facts(model, store=EvidenceStore(args.vectors), saved=saved,
            movie_id=args.movie_id, snapshots=[a[0] for a in articles], index_only=args.index_only)
    if saved != store.load(args.movie_id):
        raise ValueError('Collection changed during nonpublishing inspection')
    report['source_cache'] = {snapshot.source.source_id:state for snapshot,state in articles}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'candidates':len(report['candidates']),
        'eligible_for_review':sum(c['eligible_for_review'] for c in report['candidates']),
        'errors':len(report['errors']), 'seconds':report['seconds'], 'published':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie-id',type=int,default=329865)
    parser.add_argument('--database',type=Path,default=DEFAULT_PATH)
    parser.add_argument('--cache',type=Path,default=DEFAULT_CACHE)
    parser.add_argument('--vectors',type=Path,default=Path('../.cache/evidence'))
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--refresh',action='store_true',help='Explicitly fetch reviewed article URLs')
    parser.add_argument('--index-only',action='store_true')
    parser.add_argument('--selection',type=Path,help='Publish only the inspected IDs pinned to this report hash')
    args=parser.parse_args()
    if args.report.suffix != '.json' or (args.selection and (args.refresh or args.index_only)):
        parser.error('Use a JSON report and separate inspection/publication modes')
    asyncio.run(prepare(args))
