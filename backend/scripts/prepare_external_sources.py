"""Explicitly enrich a published collection without replacing its quiz questions."""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path

import httpx

from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.external_content import FACT_ID, compile_external_fact, reading_sources
from movie_companion.external_sources import fetch_caltech_article, fetch_script_provenance

HEADERS = {'User-Agent': 'MovieCompanionLearning/0.1 (local educational source reader)'}


async def prepare(args):
    store = ContentStore(args.database)
    saved = store.load(157336)
    if saved is None:
        raise ValueError('Prepare the starter collection first')
    if not args.refresh and any(f.id == FACT_ID for f in saved['facts'].items) and len(saved['facts'].reading_sources) == 2:
        print('Existing external sources retained; no network or model calls.')
        return
    async with httpx.AsyncClient(base_url='https://authors.library.caltech.edu', timeout=30, trust_env=False, follow_redirects=False, headers=HEADERS) as caltech, httpx.AsyncClient(base_url='https://imsdb.com', timeout=30, trust_env=False, follow_redirects=False, headers=HEADERS) as imsdb:
        async with asyncio.timeout(65):
            # Independent reviewed reads only; no generated URL or page traversal.
            article, script = await asyncio.gather(fetch_caltech_article(caltech, movie_id=157336), fetch_script_provenance(imsdb, movie_id=157336))
    fact = compile_external_fact(article)
    facts = saved['facts'].model_copy(deep=True)
    facts.items = [f for f in facts.items if f.id != FACT_ID] + [fact]
    facts.reading_sources = reading_sources(article, script)
    manifest = {c.revision: c.source_ref for item in [*saved['quiz'].items, *facts.items] for c in item.citations}
    store.publish(157336, version=saved['version'] + '+external-v1' if '+external-v1' not in saved['version'] else saved['version'], source_revision=saved['source_revision'], source_manifest=manifest, quiz=saved['quiz'], facts=facts, expected_prepared_at=saved['prepared_at'])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'article_url': article.source.source_ref, 'article_revision': article.source.revision, 'publisher': article.publisher, 'authors': article.authors, 'published_at': article.published_at, 'retrieved_at': article.retrieved_at, 'script': asdict(script), 'script_eligible_for_quiz': script.eligible_for_quiz, 'fact_count': len(facts.items), 'quiz_preserved': True}, indent=2) + '\n')
    print(f'Published {len(facts.items)} facts and two reading links; all existing quiz questions retained. Screenplay is excluded from quiz evidence.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--refresh', action='store_true', help='Refresh reviewed external sources; retain all quiz questions')
    parser.add_argument('--report', type=Path)
    asyncio.run(prepare(parser.parse_args()))
