"""Compare local role profiles on unchanged consumed quiz development controls."""
import argparse,asyncio,json,hashlib
from pathlib import Path
from time import monotonic
import httpx
from movie_companion.quiz_novelty import review_quiz_novelty
from movie_companion.content_proposals import QuizProposal
from movie_companion.local_models import DIGESTS

async def main(args):
    if args.output.exists():raise ValueError('Use a new report')
    source=Path(__file__).parents[1]/'src/movie_companion/quiz_novelty.py'
    initial=hashlib.sha256(source.read_bytes()).hexdigest()
    data=json.loads(args.dataset.read_text())
    rows=[]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False,trust_env=False,timeout=120) as client:
        for case in data['quizzes']:
            proposals=[QuizProposal(question=p['question'],options=[p['answer'],'Another detail','A different detail','An unrelated detail'],correct_index=0,passage_id='P1',evidence_quote='This fixture evaluates topic/wording review, not factual support.') for p in case['candidates']]
            began=monotonic();error=None;reviews=[]
            try:reviews=await review_quiz_novelty(client,candidates=proposals,existing=case['existing'],model=args.model)
            except (ValueError,httpx.HTTPError,TimeoutError) as exc:error=type(exc).__name__
            ready=[r.candidate_id for r in reviews if r.novelty=='new' and r.clarity=='clear']
            passed=error is None and ready==case['expected_ready_ids']
            rows.append({'id':case['id'],'expected_ready_ids':case['expected_ready_ids'],'ready_ids':ready,'passed':passed,'reviews':[r.record() for r in reviews],'error_type':error,'seconds':round(monotonic()-began,3)})
            print(f"{'PASS' if passed else 'FAIL'} {case['id']}",flush=True)
    report={'model':args.model,'model_digest':DIGESTS[args.model],'initial_module_sha256':initial,'code_changed_during_run':initial!=hashlib.sha256(source.read_bytes()).hexdigest(),'dataset_sha256':hashlib.sha256(args.dataset.read_bytes()).hexdigest(),'cases':rows,'summary':{'passed':sum(r['passed'] for r in rows),'total':len(rows)},'scope':'Consumed development role comparison, not a holdout or publication qualification'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as output:output.write(json.dumps(report,indent=2)+'\n')
    print(report['summary'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',choices=['llama3.2:3b','qwen3.5:9b'],required=True);p.add_argument('--dataset',type=Path,default=Path('../evals/movie-rag/research/readiness-cases-v2.json'));p.add_argument('--output',type=Path,required=True);asyncio.run(main(p.parse_args()))
