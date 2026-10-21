"""Compare nonpublishing research inspections on fixed cached movie sources."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

import httpx

from movie_companion.background_articles import DEFAULT_CACHE
from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.evidence_store import EvidenceStore
from movie_companion.movie_research import research_movie, source_loaders
from movie_companion.research_preparation import implementation_hashes, inspect_research


def content_hash(saved):
    body = {k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in saved.items()}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def content_projection(run):
    """Compare content without cache-state or elapsed-time noise."""
    branches = []
    for branch in run['preparation']['branches']:
        result = branch['result']
        branches.append({'purpose': branch['purpose'], 'state': branch['state'],
            'content': None if result is None else (
                {'evidence': result['evidence'], 'proposals': result['proposals'],
                 'review': result['review'], 'checks': result['checks'],
                 'eligible': result['eligible_for_review']} if branch['purpose'] == 'story' else
                {'candidates': result['candidates'], 'errors': result['errors']})})
    return branches


async def main(args):
    if args.report.exists() or args.report.suffix != '.json':
        raise ValueError('Use a new JSON report path; historical outputs cannot be overwritten')
    initial = implementation_hashes()
    bank = ContentStore(args.database)
    saved = bank.load(args.movie_id)
    if saved is None:
        raise ValueError('A saved movie collection is required for novelty comparison')
    before = content_hash(saved)
    store = EvidenceStore(args.vectors)
    modes = ['sequential', 'parallel'] if args.compare else [args.mode]
    if args.order == 'parallel-first':
        modes.reverse()
    report = {'type': 'development scheduling and draft inspection, not quality qualification',
              'movie_id': args.movie_id, 'cached_sources': True, 'runs': [],
              'published': False, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'initial_module_hashes': initial,
              'limitations': ['Cached reads do not measure live internet latency.',
                  'Fixed execution order can include model/index warm-up bias.',
                  'Equal inputs and necessary checks do not establish semantic accuracy.',
                  'Local model work stays sequential; these are specialists, not autonomous browsing agents.',
                  'Only the internal CLI uses this workflow; existing HTTP jobs remain Wikipedia-only.']}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                trust_env=False, follow_redirects=False) as client:
        for mode in modes:
            loaders = source_loaders(args.movie_id, sources=args.sources, article_cache=args.articles)
            research = await research_movie(movie_id=args.movie_id, story_loader=loaders[0],
                background_loader=loaders[1], mode=mode)
            print(f'{mode}: source branches joined; inspecting drafts serially.', flush=True)
            preparation = await inspect_research(client, research=research, store=store, saved=saved)
            run = {'mode': mode, 'research': research.trace(), 'preparation': preparation,
                   'total_seconds': round(research.seconds+preparation['seconds'], 6)}
            report['runs'].append(run)
            print(f"{mode}: {[b['state'] for b in preparation['branches']]}; {run['total_seconds']}s", flush=True)
    report['code_changed_during_run'] = initial != implementation_hashes()
    report['saved_bank_unchanged'] = before == content_hash(bank.load(args.movie_id))
    if len(report['runs']) == 2:
        left, right = report['runs']
        manifest = lambda r: [{k: b[k] for k in ('purpose', 'status', 'errors', 'sources')}
                               for b in r['research']['branches']]
        report['comparison'] = {'same_source_inputs': manifest(left) == manifest(right),
            'same_inspected_outputs': content_projection(left) == content_projection(right),
            'source_seconds': {r['mode']: r['research']['seconds'] for r in report['runs']},
            'total_seconds': {r['mode']: r['total_seconds'] for r in report['runs']}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x') as output:
        output.write(json.dumps(report, indent=2)+'\n')
    if report['code_changed_during_run'] or not report['saved_bank_unchanged']:
        raise ValueError('Code or saved bank changed during inspection; inspect the saved report')
    if args.compare and not report['comparison']['same_source_inputs']:
        raise ValueError('Comparison source inputs changed; inspect the saved report')
    if any(b['state'] == 'failed' or b['state'] == 'timed_out'
           for r in report['runs'] for b in r['preparation']['branches']):
        raise ValueError('A draft inspection failed; inspect the saved report')
    print(f'Nonpublishing report saved to {args.report}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie-id', type=int, default=329865)
    parser.add_argument('--database', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--sources', type=Path, default=Path('../.cache/source-snapshots'))
    parser.add_argument('--articles', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--vectors', type=Path, default=Path('data/private/research-inspection'))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--mode', choices=['sequential', 'parallel'], default='parallel')
    parser.add_argument('--compare', action='store_true')
    parser.add_argument('--order', choices=['sequential-first', 'parallel-first'], default='sequential-first')
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, OSError, httpx.HTTPError, TimeoutError) as error:
        raise SystemExit(f'Research inspection stopped ({type(error).__name__}). Saved content was not published.') from error
