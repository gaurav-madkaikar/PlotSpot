"""Explicit local API reuse/refresh proof; does not publish drafts."""
import asyncio
from pathlib import Path
from time import monotonic
import httpx
from movie_companion.content_store import ContentStore
from movie_companion.research_checkpoint import bank_identity,workflow_hash
from movie_companion.preparation_jobs import atomic_json

OUTPUT=Path('../evals/movie-rag/research/live-durable-arrival-v1.json')

async def main():
    if OUTPUT.exists():raise ValueError('Use a fresh runtime artifact')
    bank=ContentStore()
    before={m:bank_identity(bank.load(m)) for m in (27205,157336,329865,603,546554,496243,129,37165,120467,438631,155)}
    report={'movie_id':329865,'bank_hashes_before':before,'workflow_sha256':workflow_hash(),'events':[],'published':False}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=20,trust_env=False) as client:
        spoiler=await client.post('/api/movies/329865/preparation',json={'refresh':True})
        assert spoiler.status_code==403
        report['spoiler_consent_status']=spoiler.status_code
        response=await client.post('/api/movies/329865/preparation',json={'allow_spoilers':True})
        response.raise_for_status()
        for _ in range(40):
            status=(await client.get('/api/movies/329865/preparation?allow_spoilers=true')).json()['job']
            if status['state']=='ready':break
            await asyncio.sleep(.1)
        assert status['state']=='ready'
        report['reuse']=status
        response=await client.post('/api/movies/329865/preparation',json={'allow_spoilers':True,'refresh':True})
        response.raise_for_status()
        job_id=response.json()['job']['id'];report['job_id']=job_id
        repeated=await client.post('/api/movies/329865/preparation',json={'allow_spoilers':True,'refresh':True})
        assert repeated.json()['job']['id']==job_id
        report['duplicate_start_same_id']=True
        began=monotonic();last=None
        while monotonic()-began<630:
            status=(await client.get('/api/movies/329865/preparation?allow_spoilers=true')).json()['job']
            assert status['id']==job_id
            marker=(status['state'],status['phase'],status['batches_completed'],status['facts_retained'],status['questions_retained'])
            if marker!=last:
                report['events'].append({'seconds':round(monotonic()-began,3),'state':status['state'],'phase':status['phase'],
                    'completed':status['batches_completed'],'facts':status['facts_retained'],'questions':status['questions_retained']})
                last=marker;atomic_json(OUTPUT,report);print(marker,flush=True)
            assert bank_identity(bank.load(329865))==before[329865]
            if status['state'] not in ('queued','running'):break
            await asyncio.sleep(2)
        report['final_status']=status;report['seconds']=round(monotonic()-began,3)
        report['bank_hashes_after_preparation']={m:bank_identity(bank.load(m)) for m in before}
        report['bank_unchanged_until_review']=report['bank_hashes_after_preparation']==before
        atomic_json(OUTPUT,report)
        print('TERMINAL',status['state'],status['facts_retained'],status['questions_retained'],flush=True)

asyncio.run(main())
