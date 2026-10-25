"""Bounded local two-batch restart inspection, isolated from published content."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

import httpx

from movie_companion.content_preparation import prepare_drafts
from movie_companion.content_store import DEFAULT_PATH
from movie_companion.evidence_store import SourceDocument
from movie_companion.local_models import verify_local_model
from movie_companion.preparation_jobs import PreparationJobs
from movie_companion.proposal_evidence import evidence_pools
from movie_companion.story_rag import policy_fingerprint
from movie_companion.background_fact_workflow import fingerprint as background_fingerprint


def saved_hash():
    with sqlite3.connect(DEFAULT_PATH.as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute('SELECT movie_id,version,prepared_at,source_revision,payload FROM collections ORDER BY movie_id').fetchall()
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()


async def inspect(args):
    if args.output.exists() or args.output.suffix!='.json':raise ValueError('Use a new JSON inspection path')
    source=SourceDocument(**json.loads(args.source.read_text()))
    evidence_pools(source)
    before=saved_hash();story=policy_fingerprint();background=background_fingerprint()
    result={'state':'running','published':False,'movie_id':source.movie_id,'source_revision':source.revision,
            'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'model':'qwen3.5:9b',
            'limitations':'Real local inference on two fixed section batches, with a temporary SQLite queue and injected bounded runner. Exercises graceful shutdown/startup and coordinator resume, not SIGKILL recovery, independent semantic accuracy, full RAG retrieval, or production load.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as file:file.write(json.dumps(result,indent=2)+'\n')
    def save():args.output.write_text(json.dumps(result,indent=2)+'\n')
    try:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,trust_env=False,follow_redirects=False) as client:
            await verify_local_model(client,'qwen3.5:9b')
            with TemporaryDirectory(prefix='movie-preparation-recovery-') as directory:
                slot=asyncio.Lock();first_saved=asyncio.Event();second_finished=asyncio.Event()
                snapshots=[];final=[]
                async def first_runner(movie_id,checkpoint):
                    def record(report):
                        checkpoint(report)
                        if len(report['batches'])==1 and report['state']=='running':
                            snapshots.append(copy.deepcopy(report));first_saved.set()
                    return await prepare_drafts(client,source=source,model='qwen3.5:9b',review_model='qwen3.5:9b',
                        max_batches=2,deadline_seconds=240,checkpoint=record)
                original=PreparationJobs(None,client,slot,root=Path(directory),runner=first_runner)
                restarted=None
                try:
                    started=await original.start(source.movie_id)
                    await asyncio.wait_for(first_saved.wait(),240)
                    await original.close()
                    paused=original.status(source.movie_id).job
                    result['paused']={'job_id':paused.id,'state':paused.state,'completed_batches':paused.batches_completed}
                    result['first_completed_batch']=snapshots[-1]['batches'][0]
                    save()
                    async def second_runner(movie_id,checkpoint):
                        report=await prepare_drafts(client,source=source,model='qwen3.5:9b',review_model='qwen3.5:9b',
                            max_batches=2,deadline_seconds=240,checkpoint=checkpoint,resume=restarted.active['report'])
                        final.append(report);second_finished.set()
                        return report
                    restarted=PreparationJobs(None,client,slot,root=Path(directory),runner=second_runner)
                    await restarted.open()
                    await asyncio.wait_for(second_finished.wait(),240)
                    await restarted.task
                    completed=restarted.status(source.movie_id).job
                    result['resumed']={'job_id':completed.id,'state':completed.state,'completed_batches':completed.batches_completed}
                    result['final_report']=final[0]
                    result['same_job_id']=started.job.id==paused.id==completed.id
                    result['first_batch_preserved']=final[0]['batches'][0]==snapshots[-1]['batches'][0]
                    result['state']='complete' if result['same_job_id'] and result['first_batch_preserved'] and len(final[0]['batches'])==2 else 'incomplete'
                finally:
                    await original.close()
                    if restarted:await restarted.close()
    except (ValueError,OSError,httpx.HTTPError,TimeoutError) as error:
        result.update(state='failed',error_type=type(error).__name__)
    finally:
        result['saved_content_unchanged']=saved_hash()==before
        result['story_policy_unchanged']=policy_fingerprint()==story
        result['background_policy_unchanged']=background_fingerprint()==background
        save()
    print(json.dumps({key:value for key,value in result.items() if key not in {'final_report','first_completed_batch'}},indent=2))
    if result['state']!='complete':raise SystemExit('Recovery inspection did not complete; report preserved.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(inspect(parser.parse_args()))
