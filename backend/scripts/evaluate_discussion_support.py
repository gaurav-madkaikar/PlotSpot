"""Explicit local reviewer controls; no automatic qualification or publication."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import httpx
from movie_companion import discussion_support

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'evals/grounding/support-review-cases.json'


async def evaluate(output, dataset=DATA):
    if output.resolve() == dataset.resolve() or output.suffix != '.json':
        raise ValueError('Use a distinct JSON report')
    data = json.loads(dataset.read_text())
    rows = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False) as client:
        tags = await client.get('/api/tags'); tags.raise_for_status()
        digest = next((m['digest'] for m in tags.json()['models'] if m['name'] == discussion_support.MODEL), None)
        for case in data['cases']:
            started = perf_counter(); verdict = None; error = None
            try:
                verdict = await discussion_support.review_support(client, model=discussion_support.MODEL,
                    question=case['question'], answer=case['answer'], quotes=case['quotes'])
            except (ValueError, httpx.HTTPError) as exc:
                error = type(exc).__name__
            accepted = verdict is not None and verdict.verdict == 'supported'
            passed = error is None and accepted == case['expected_supported']
            rows.append({'id': case['id'], 'expected_supported': case['expected_supported'],
                         'review': asdict(verdict) if verdict else None, 'error': error,
                         'automated_pass': passed, 'duration_seconds': round(perf_counter()-started, 3)})
            print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {verdict}", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'policy': discussion_support.POLICY, 'model': discussion_support.MODEL, 'model_digest': digest,
        'reviewer_sha256': hashlib.sha256(Path(discussion_support.__file__).read_bytes()).hexdigest(),
        'dataset_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(), 'split': data['split'],
        'summary': {'passed': sum(r['automated_pass'] for r in rows), 'total': len(rows),
                    'false_acceptances': sum(r['expected_supported'] is False and r['review'] is not None and r['review']['verdict']=='supported' for r in rows),
                    'false_rejections': sum(r['expected_supported'] is True and not r['automated_pass'] for r in rows)},
        'limitations': ['Consumed assistant-authored development controls, not an independent safety benchmark.',
                       'A distinct model reviews; model errors can still be correlated.',
                       'A supported verdict is not proof or an automatic-publication qualification.'],
        'cases': rows}, indent=2)+'\n')
    return int(not all(r['automated_pass'] for r in rows))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=DATA)
    args=parser.parse_args()
    raise SystemExit(asyncio.run(evaluate(args.output, args.dataset)))
