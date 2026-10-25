"""Review retrieved quiz-replacement evidence with the pinned local model."""

import argparse,asyncio
from datetime import datetime,timezone
import json
from pathlib import Path

import httpx

from movie_companion.local_models import DIGESTS,verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_evidence_review import MODEL,POLICY,review_evidence
from movie_companion.research_checkpoint import digest


async def run(args):
    source=json.loads(args.input.read_text())
    if source.get('status')!='proposal_only' or source.get('published') is not False:
        raise ValueError('Expected non-publishing evidence retrieval')
    rows=[]
    if args.output.is_file():
        checkpoint=json.loads(args.output.read_text())
        if checkpoint.get('status')=='running' and checkpoint.get('planned')==len(source['items']):
            rows=checkpoint['items']
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=args.timeout,
                                 trust_env=False,follow_redirects=False) as client:
        await verify_local_model(client,MODEL)
        for start in range(len(rows),len(source['items']),3):
            batch=source['items'][start:start+3]
            decisions=await review_evidence(client,batch)
            for target,decision in zip(batch,decisions.items,strict=True):
                selected=[target['evidence'][int(alias[1:])-1] for alias in decision.evidence_ids]
                rows.append({'movie_id':target['movie_id'],'title':target['title'],
                    'question_id':target['question_id'],'replacement_brief':target['replacement_brief'],
                    'status':decision.status,'reason':decision.reason,'selected_evidence':selected})
            atomic_json(args.output,{'status':'running','policy':POLICY,'planned':len(source['items']),
                'completed':len(rows),'items':rows,'published':False})
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'policy':POLICY,
        'status':'proposal_only','published':False,'source_report_sha256':digest(source),
        'model':MODEL,'model_digest':DIGESTS[MODEL],
        'summary':{'targets':len(rows),'supported':sum(row['status']=='supported' for row in rows),
                   'insufficient':sum(row['status']=='insufficient' for row in rows)},
        'items':rows,'publication':{'authorized':False,'database_mutated':False}}
    atomic_json(args.output,report);print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=180)
    asyncio.run(run(parser.parse_args()))
