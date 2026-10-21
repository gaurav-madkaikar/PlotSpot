"""Inspect real-film quiz generation without writing to the saved content database."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
from time import monotonic

import httpx
import movie_companion.story_rag as rag
from chromadb.errors import ChromaError

from movie_companion.content_store import ContentStore
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.movie_questions import MovieQuestionService
from movie_companion.preparation_jobs import atomic_json
from movie_companion.story_rag import StoryRag, policy_fingerprint
from movie_companion.story_verification import MODEL, POLICY
from movie_companion.local_models import DIGESTS
from movie_companion.screenplay_source import SCRIPTS


async def evaluate(args):
    report = {'policy': POLICY, 'model': MODEL, 'model_digest':DIGESTS[MODEL], 'implementation_sha256': policy_fingerprint(),
              'published': False, 'evaluation_kind': 'real_movie_development_inspection',
              'evidence_store_mode': 'isolated_evaluation', 'movies': []}
    atomic_json(args.report, report)
    released_store = await asyncio.to_thread(EvidenceStore, args.evidence_store/'released')
    async with httpx.AsyncClient(base_url='https://en.wikipedia.org', timeout=40, trust_env=False, follow_redirects=False) as wiki, \
               httpx.AsyncClient(base_url='https://imsdb.com', timeout=40, trust_env=False, follow_redirects=False) as scripts, \
               httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False, follow_redirects=False) as model:
        for movie_id in args.movies:
            source_path = args.snapshots / f'{movie_id}.json'
            if source_path.stat().st_size > 1_000_000 or source_path.resolve() == args.report.resolve():
                raise ValueError('Invalid source snapshot/report destination')
            source = SourceDocument(**json.loads(source_path.read_text()))
            if source.movie_id != movie_id:
                raise ValueError('Wrong source movie')
            saved = ContentStore().load(movie_id)
            if saved is None:
                raise ValueError('A saved quiz is required')
            service = MovieQuestionService(wiki, model, store=released_store)
            service.source_cache[movie_id] = (monotonic() + 300, source)
            story = StoryRag(scripts, evidence_path=args.evidence_store/'scripts')
            audits = []
            original_audit = story.audit
            seeds = []
            original_seed = rag.propose_quiz_seed
            async def capture_seed(*args,**kwargs):
                result = await original_seed(*args,**kwargs)
                seeds.extend(s.model_dump() for s in result.items)
                return result
            rag.propose_quiz_seed = capture_seed

            def capture(context, *, mode, decisions, drafts):
                original_audit(context, mode=mode, decisions=decisions, drafts=drafts)
                # Report candidate wording and released-film citations for human review;
                # never copy full screenplay excerpts to a public report.
                audits.append({'trace': context.trace, 'decisions': copy.deepcopy(decisions),
                    'candidates': [d.model_dump(exclude={'script_quote'}) for d in drafts.items]})

            story.audit = capture
            started = monotonic()
            try:
                async with asyncio.timeout(180):
                    source, passages = await service.load_evidence(movie_id)
                    questions = await story.quiz(model, source=source, passages=passages, existing=saved['quiz'])
                result = {'movie_id': movie_id, 'source_revision': source.revision,
                          'accepted': [q.model_dump() for q in questions], 'error': None}
            except (ValueError, httpx.HTTPError, ChromaError, TimeoutError) as error:
                result = {'movie_id': movie_id, 'accepted': [], 'error': type(error).__name__}
            # Inspection must not change saved content, including on errors.
            if saved != ContentStore().load(movie_id):
                raise ValueError('Inspection unexpectedly changed saved content')
            rag.propose_quiz_seed = original_seed
            result.update(seconds=round(monotonic() - started, 2), audits=audits, seeds=seeds)
            report['movies'].append(result)
            atomic_json(args.report, report)
            print(f"{movie_id}: {len(result['accepted'])} accepted; error={result['error']}; {result['seconds']}s", flush=True)
    report['totals'] = {'movies': len(report['movies']),
                        'accepted': sum(len(r['accepted']) for r in report['movies']),
                        'seeds': sum(len(r['seeds']) for r in report['movies']),
                        'candidates': sum(len(a['candidates']) for r in report['movies'] for a in r['audits']),
                        'attempt_errors': sum('error' in d for r in report['movies'] for a in r['audits'] for d in a['decisions']),
                        'errors': sum(r['error'] is not None for r in report['movies'])}
    if report['implementation_sha256'] != policy_fingerprint():
        raise ValueError('Implementation changed during this inspection')
    atomic_json(args.report, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movies', type=int, nargs='+', choices=sorted(SCRIPTS), default=[27205, 603])
    parser.add_argument('--snapshots', type=Path, default=Path('../.cache/source-snapshots'))
    parser.add_argument('--evidence-store', type=Path, default=Path('data/private/story-quiz-eval-evidence'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.suffix != '.json' or len(args.movies) > 3 or len(set(args.movies)) != len(args.movies):
        parser.error('Use a JSON report and one to three distinct movies')
    asyncio.run(evaluate(args))
