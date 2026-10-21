"""Generate a second replacement pass from reviewed broader story evidence."""

import argparse,asyncio
from datetime import datetime,timezone
import json
from pathlib import Path

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.local_models import DIGESTS,verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_workflow import MODEL,build_targets,generate_drafts,review_drafts
from movie_companion.research_checkpoint import digest


POLICY='saved-quiz-replacement-broader-evidence-v1'


async def run(args):
    source_review=json.loads(args.source_review.read_text())
    evidence_review=json.loads(args.evidence_review.read_text())
    if (evidence_review.get('policy')!='assistant-replacement-evidence-editorial-v1'
            or evidence_review.get('status')!='proposal_only' or evidence_review.get('published') is not False):
        raise ValueError('Expected the assistant-reviewed broader evidence')
    targets={target['question_id']:target for target in build_targets(source_review,ContentStore(args.database))}
    work=[]
    for selection in evidence_review['items']:
        if selection['editorial_decision']!='accept':continue
        target={**targets[selection['question_id']]}
        target['evidence']={'explanation':target['replacement_brief'],'citations':[
            {key:item[key] for key in ('source_label','source_ref','revision','excerpt')}
            for item in selection['selected_evidence']]}
        work.append(target)
    rows=[]
    if args.output.is_file():
        checkpoint=json.loads(args.output.read_text())
        if checkpoint.get('status')=='running' and checkpoint.get('planned')==len(work):rows=checkpoint['items']
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=args.timeout,
                                 trust_env=False,follow_redirects=False) as client:
        await verify_local_model(client,MODEL)
        for start in range(len(rows),len(work),3):
            batch=work[start:start+3]
            drafts=await generate_drafts(client,targets=batch)
            reviewed=await review_drafts(client,targets=batch,drafts=drafts)
            for row in reviewed:
                target=batch[int(row['target_id'][1:])-1]
                rows.append({'movie_id':target['movie_id'],'title':target['title'],
                    'question_id':target['question_id'],'old_question':target['old_question'],
                    'replacement_brief':target['replacement_brief'],'reviewed_evidence':target['evidence'],
                    **{key:value for key,value in row.items() if key!='target_id'}})
            atomic_json(args.output,{'status':'running','policy':POLICY,'planned':len(work),
                'completed':len(rows),'items':rows,'published':False})
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'policy':POLICY,
        'status':'proposal_only','published':False,'source_review_sha256':digest(source_review),
        'evidence_review_sha256':digest(evidence_review),'model':MODEL,'model_digest':DIGESTS[MODEL],
        'summary':{'targets':len(rows),'writer_drafts':sum(row['candidate'] is not None for row in rows),
            'deterministic_passes':sum(row['candidate'] is not None and not row['deterministic_problems'] for row in rows),
            'critic_accepts':sum(row['ready_for_assistant_review'] for row in rows)},
        'items':rows,'publication':{'authorized':False,'database_mutated':False}}
    atomic_json(args.output,report);print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-review',type=Path,required=True)
    parser.add_argument('--evidence-review',type=Path,required=True)
    parser.add_argument('--database',type=Path,default=Path('data/movie-content.db'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=180)
    asyncio.run(run(parser.parse_args()))
