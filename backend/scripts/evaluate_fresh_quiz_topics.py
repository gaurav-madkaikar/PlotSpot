"""Run untouched pairs against separately frozen, blinded reviewer labels."""
import argparse,asyncio,hashlib,json
from pathlib import Path
from time import monotonic
import httpx
from movie_companion.content_proposals import QuizProposal
from movie_companion.local_models import DIGESTS
from movie_companion.quiz_novelty import review_quiz_novelty
from movie_companion.research_checkpoint import workflow_hash
from movie_companion.preparation_jobs import atomic_json

async def main(args):
    if args.output.exists():raise ValueError('Use a new report')
    data=json.loads(args.dataset.read_text());labels=json.loads(args.labels.read_text())
    if hashlib.sha256(args.dataset.read_bytes()).hexdigest()!=labels['dataset_sha256']:raise ValueError('Review inputs changed')
    initial=workflow_hash();report={'dataset_sha256':labels['dataset_sha256'],
        'labels_sha256':hashlib.sha256(args.labels.read_bytes()).hexdigest(),'review_kind':labels['review_kind'],
        'model':'qwen3.5:9b','model_digest':DIGESTS['qwen3.5:9b'],'workflow_sha256':initial,
        'cases':[],'published':False,'scope':labels['limitations']}
    atomic_json(args.output,report)
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,trust_env=False,follow_redirects=False) as client:
        for case in data['cases']:
            p=case['candidate'];began=monotonic();error=None;reviews=[]
            proposal=QuizProposal(question=p['question'],options=[p['answer'],'Other detail','Different detail','Unrelated detail'],
                correct_index=0,passage_id='P1',evidence_quote='Fictional topic-only evaluation; not a source-support test.')
            try:reviews=await review_quiz_novelty(client,candidates=[proposal],existing=case['existing'])
            except (ValueError,httpx.HTTPError,TimeoutError) as exc:error=type(exc).__name__
            actual=None
            if reviews:
                r=reviews[0]
                actual='DUPLICATE' if r.novelty=='duplicate' else 'NEW' if r.novelty=='new' and r.clarity=='clear' else 'UNCLEAR'
            row={'id':case['id'],'expected':labels['labels'][case['id']],'actual':actual,'reviews':[r.record() for r in reviews],
                 'passed':actual==labels['labels'][case['id']] and error is None,'error_type':error,'seconds':round(monotonic()-began,3)}
            report['cases'].append(row);atomic_json(args.output,report);print(f"{'PASS' if row['passed'] else 'FAIL'} {row['id']} {actual}",flush=True)
    report['summary']={'passed':sum(r['passed'] for r in report['cases']),'total':len(report['cases'])}
    report['code_changed_during_run']=initial!=workflow_hash();atomic_json(args.output,report);print(report['summary'])
    if report['code_changed_during_run']:raise ValueError('Policy changed during run')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,default=Path('../evals/movie-rag/research/fresh-topic-review.json'))
    p.add_argument('--labels',type=Path,default=Path('../evals/movie-rag/research/fresh-topic-labels-ai-v1.json'));p.add_argument('--output',type=Path,required=True)
    asyncio.run(main(p.parse_args()))
