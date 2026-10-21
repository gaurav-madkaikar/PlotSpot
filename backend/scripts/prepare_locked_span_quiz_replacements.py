"""Prepare non-publishing replacement drafts with code-locked answer spans."""

import argparse,asyncio
from datetime import datetime,timezone
import json
from pathlib import Path

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.local_models import DIGESTS,verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_span_writer import MODEL,POLICY,answer_spans,generate_locked_drafts
from movie_companion.quiz_replacement_workflow import build_targets,review_drafts
from movie_companion.research_checkpoint import digest


async def run(args):
    source_review=json.loads(args.source_review.read_text());evidence_review=json.loads(args.evidence_review.read_text())
    targets={target['question_id']:target for target in build_targets(source_review,ContentStore(args.database))}
    work=[]
    for selection in evidence_review['items']:
        if selection['editorial_decision']!='accept':continue
        target={**targets[selection['question_id']]};target['evidence']={
            'explanation':target['replacement_brief'],'citations':[
                {key:item[key] for key in ('source_label','source_ref','revision','excerpt')}
                for item in selection['selected_evidence']]}
        work.append(target)
    rows=[]
    if args.output.is_file():
        checkpoint=json.loads(args.output.read_text())
        if (checkpoint.get('status')=='running' and checkpoint.get('policy')==POLICY
                and checkpoint.get('planned')==len(work)):
            rows=checkpoint['items']
    completed={row['question_id'] for row in rows}
    pending=[]
    for target in work:
        if target['question_id'] in completed:continue
        spans=answer_spans(target)
        if spans:
            pending.append(target);continue
        rows.append({'movie_id':target['movie_id'],'title':target['title'],
            'question_id':target['question_id'],'old_question':target['old_question'],
            'replacement_brief':target['replacement_brief'],'reviewed_evidence':target['evidence'],
            'answer_spans':[],'candidate':None,
            'deterministic_problems':['no_natural_exact_answer_span'],'critic':None,
            'ready_for_assistant_review':False})
        atomic_json(args.output,{'status':'running','policy':POLICY,'planned':len(work),
            'completed':len(rows),'items':rows,'published':False})
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=args.timeout,
                                 trust_env=False,follow_redirects=False) as client:
        await verify_local_model(client,MODEL)
        for start in range(0,len(pending),3):
            batch=pending[start:start+3];drafts,writer_info=await generate_locked_drafts(client,batch)
            reviewed=await review_drafts(client,targets=batch,drafts=drafts)
            reviewed_by_alias={row['target_id']:row for row in reviewed}
            for index,target in enumerate(batch):
                alias=f'T{index+1}'
                if not writer_info[alias]['writer_problems']:continue
                reviewed_by_alias[alias]={'target_id':alias,'candidate':None,
                    'deterministic_problems':writer_info[alias]['writer_problems'],
                    'critic':None,'ready_for_assistant_review':False}
            for row in sorted(reviewed_by_alias.values(),key=lambda item:int(item['target_id'][1:])):
                target=batch[int(row['target_id'][1:])-1]
                rows.append({'movie_id':target['movie_id'],'title':target['title'],
                    'question_id':target['question_id'],'old_question':target['old_question'],
                    'replacement_brief':target['replacement_brief'],'reviewed_evidence':target['evidence'],
                    'answer_spans':writer_info[row['target_id']]['answer_spans'],
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
    parser.add_argument('--source-review',type=Path,required=True);parser.add_argument('--evidence-review',type=Path,required=True)
    parser.add_argument('--database',type=Path,default=Path('data/movie-content.db'));parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=180);asyncio.run(run(parser.parse_args()))
