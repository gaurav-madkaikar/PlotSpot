import asyncio
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from movie_companion.main import app
from movie_companion.preparation_jobs import PreparationJobs, JobError, atomic_json
from movie_companion.preparation_routes import get_jobs


def report():
    return {'state':'incomplete','phase':'finished','facts':[], 'questions':[], 'batches':[]}


def test_start_reuse_single_slot_cancel_and_persistent_state(tmp_path):
    async def run():
        began=asyncio.Event()
        calls=[]
        async def runner(movie_id, checkpoint):
            calls.append(movie_id)
            checkpoint({**report(),'phase':'generating'})
            began.set()
            await asyncio.Event().wait()
        slot=asyncio.Lock()
        jobs=PreparationJobs(None,None,slot,root=tmp_path,runner=runner)
        first=await jobs.start(27205)
        assert slot.locked()
        await began.wait()
        same=await jobs.start(27205)
        assert same.job.id==first.job.id and calls==[27205]
        assert same.job.phase=='generating'
        queued=await jobs.start(603)
        assert queued.job.state=='queued'
        assert (await jobs.start(603)).job.id==queued.job.id
        assert (await jobs.cancel(603,queued.job.id)).job.state=='cancelled'
        with pytest.raises(JobError): await jobs.cancel(27205,'f'*32)
        assert slot.locked()
        cancelled=await jobs.cancel(27205,first.job.id)
        assert cancelled.job.state=='cancelled' and not slot.locked()
        restarted=PreparationJobs(None,None,slot,root=tmp_path)
        assert restarted.status(27205).job.state=='cancelled'
        await jobs.close()
    asyncio.run(run())


def test_immediate_cancellation_does_not_leak_slot(tmp_path):
    async def run():
        async def runner(*args): await asyncio.Event().wait()
        slot=asyncio.Lock()
        jobs=PreparationJobs(None,None,slot,root=tmp_path,runner=runner)
        status=await jobs.start(27205)
        result=await jobs.cancel(27205,status.job.id)
        assert result.job.state=='cancelled' and not slot.locked()
    asyncio.run(run())


def test_completion_reads_never_generate_and_shutdown_cancels(tmp_path):
    async def run():
        calls=[]
        async def runner(movie_id, checkpoint):
            calls.append(movie_id)
            return report()
        slot=asyncio.Lock()
        jobs=PreparationJobs(None,None,slot,root=tmp_path,runner=runner)
        assert jobs.status(27205).job is None
        await jobs.start(27205)
        await jobs.task
        for _ in range(3): assert jobs.status(27205).job.state=='incomplete'
        assert calls==[27205] and not slot.locked()
        async def pending(*args): await asyncio.Event().wait()
        jobs.runner=pending
        await jobs.start(603)
        await jobs.close()
        assert jobs.status(603).job.state=='queued' and not slot.locked()
    asyncio.run(run())


def test_interrupted_checkpoint_recovers_without_restarting_model(tmp_path):
    record={'id':'a'*32,'movie_id':27205,'state':'running','phase':'reviewing',
            'updated_at':'2026-10-11T00:00:00Z','message':'Checking drafts.','report':report()}
    atomic_json(tmp_path/'27205.json',record)
    jobs=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path)
    assert jobs.status(27205).job.state=='interrupted'
    # Legacy files remain unchanged; migrated status is held in SQLite.
    assert json.loads((tmp_path/'27205.json').read_text())['state']=='running'
    assert jobs.status(999).available is False


def test_worker_error_and_busy_shared_slot_are_safe(tmp_path):
    async def run():
        async def runner(*args): raise ValueError('Secret raw model response should not be returned')
        slot=asyncio.Lock()
        jobs=PreparationJobs(None,None,slot,root=tmp_path,runner=runner)
        await slot.acquire()
        queued=await jobs.start(27205)
        assert queued.job.state=='queued'
        slot.release()
        await jobs.start(27205)
        await jobs.task
        status=jobs.status(27205)
        assert status.job.state=='failed' and 'Secret' not in status.job.message
        assert not slot.locked()
        await jobs.close()
    asyncio.run(run())


def test_projection_retains_rejected_drafts_and_trusted_source_text(tmp_path):
    raw=json.loads((Path(__file__).parents[2]/'evals/movie-rag/preparation-inception-purpose-branches-one-batch.json').read_text())
    record={'id':'a'*32,'movie_id':27205,'state':'incomplete','phase':'finished',
            'updated_at':'2026-10-11T00:00:00Z','message':'Review drafts.','report':raw}
    atomic_json(tmp_path/'27205.json',record)
    jobs=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path)
    result=jobs.status(27205).job
    assert len(result.items)==4 and result.questions_retained==0
    assert result.items[-1].decision=='reject'
    assert not result.publication_approved
    corrupted=copy.deepcopy(record)
    corrupted['report']['batches'][0]['evidence'][0]['origin']['source_ref']='javascript:alert(1)'
    with jobs.store.connection() as db:
        db.execute('UPDATE jobs SET payload=? WHERE movie_id=?',(json.dumps(corrupted),27205))
    with pytest.raises(JobError) as error: jobs.status(27205)
    assert error.value.status==503


def test_routes_require_spoiler_consent_and_reads_never_start(content_member, tmp_path):
    jobs=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path)
    app.dependency_overrides[get_jobs]=lambda:jobs
    try:
        client=content_member()
        path='/api/movies/27205/preparation'
        assert client.get(path).status_code==403
        assert client.post(path,json={'allow_spoilers':False}).status_code==403
        assert client.post(path,json={'allow_spoilers':'true'}).status_code==422
        assert client.post(path,json={'allow_spoilers':True,'source_url':'https://evil.example'}).status_code==422
        assert client.get(path+'?allow_spoilers=true').json()=={'available':True,'job':None}
        assert client.get('/api/movies/999/preparation?allow_spoilers=true').json()['available'] is False
        assert not list(tmp_path.glob('*.json'))
    finally: app.dependency_overrides.pop(get_jobs,None)


def test_atomic_write_failure_preserves_last_checkpoint(tmp_path,monkeypatch):
    path=tmp_path/'checkpoint.json'
    atomic_json(path,{'saved':True})
    previous=path.read_bytes()
    def fail(*args): raise PermissionError('Cannot replace checkpoint')
    monkeypatch.setattr(Path,'replace',fail)
    with pytest.raises(PermissionError): atomic_json(path,{'saved':False})
    assert path.read_bytes()==previous
    assert list(tmp_path.glob('.job-*'))==[]


def test_routes_start_and_cancel_pass_only_validated_movie_and_job_id(content_member):
    from movie_companion.preparation_jobs import DraftStatus
    class FakeJobs:
        def __init__(self):self.calls=[]
        async def start(self,movie_id):
            self.calls.append(('start',movie_id))
            return DraftStatus(available=True)
        async def cancel(self,movie_id,job_id):
            self.calls.append(('cancel',movie_id,job_id))
            return DraftStatus(available=True)
    jobs=FakeJobs()
    app.dependency_overrides[get_jobs]=lambda:jobs
    try:
        client=content_member()
        path='/api/movies/27205/preparation'
        assert client.post(path,json={'allow_spoilers':True}).status_code==202
        assert client.post(path+'/cancel',json={'allow_spoilers':True,'job_id':'a'*32}).status_code==200
        assert client.post(path+'/cancel',json={'allow_spoilers':True,'job_id':'../bad'}).status_code==422
        assert jobs.calls==[('start',27205),('cancel',27205,'a'*32)]
    finally:app.dependency_overrides.pop(get_jobs,None)


def test_restart_keeps_job_id_completed_checkpoint_and_fifo(tmp_path):
    async def run():
        begun=asyncio.Event()
        async def first_runner(movie_id,checkpoint):
            checkpoint({**report(),'phase':'reviewing'})
            begun.set()
            await asyncio.Event().wait()
        slot=asyncio.Lock()
        original=PreparationJobs(None,None,slot,root=tmp_path,runner=first_runner,poll_seconds=0.01)
        first=await original.start(27205);await begun.wait()
        queued=await original.start(603)
        await original.close()
        assert original.status(27205).job.state=='queued' and not slot.locked()
        calls=[];resumed=[];finished=asyncio.Event()
        async def second_runner(movie_id,checkpoint):
            calls.append(movie_id)
            resumed.append(copy.deepcopy(restarted.active['report']))
            if len(calls)==2:finished.set()
            return report()
        restarted=PreparationJobs(None,None,slot,root=tmp_path,runner=second_runner,poll_seconds=0.01)
        assert restarted.status(27205).job.id==first.job.id
        assert restarted.status(603).job.id==queued.job.id
        await restarted.open()
        await asyncio.wait_for(finished.wait(),1)
        await restarted.task
        assert calls==[27205,603] and resumed[0]['phase']=='reviewing'
        assert restarted.status(27205).job.state=='incomplete'
        await restarted.close()
    asyncio.run(run())


def test_two_managers_do_not_duplicate_runner_and_remote_cancel_is_observed(tmp_path):
    async def run():
        calls=[];begun=asyncio.Event()
        async def runner(movie_id,checkpoint):
            calls.append(movie_id);begun.set()
            await asyncio.Event().wait()
        first=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path,runner=runner,poll_seconds=0.01)
        second=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path,runner=runner,poll_seconds=0.01)
        result=await first.start(27205);await begun.wait()
        other=await second.start(27205)
        assert other.job.id==result.job.id and other.job.state=='running'
        # Status from another manager does not mark live work interrupted.
        assert second.status(27205).job.state=='running'
        await second.cancel(27205,result.job.id)
        for _ in range(30):
            if first.status(27205).job.state=='cancelled':break
            await asyncio.sleep(0.01)
        assert first.status(27205).job.state=='cancelled' and calls==[27205]
        await second.close();await first.close()
    asyncio.run(run())


def test_busy_inference_slot_queues_then_dispatches_without_another_request(tmp_path):
    async def run():
        slot=asyncio.Lock();await slot.acquire();begun=asyncio.Event()
        async def runner(movie_id,checkpoint):begun.set();return report()
        jobs=PreparationJobs(None,None,slot,root=tmp_path,runner=runner,poll_seconds=0.01)
        queued=await jobs.start(27205)
        assert queued.job.state=='queued' and not begun.is_set()
        slot.release()
        await asyncio.wait_for(begun.wait(),1)
        await jobs.task
        assert jobs.status(27205).job.state=='incomplete'
        await jobs.close()
    asyncio.run(run())


def test_mismatching_resume_stops_interrupted_without_raw_details(tmp_path):
    from movie_companion.preparation_resume import ResumeMismatch
    async def run():
        async def runner(*args):raise ResumeMismatch('Private source details')
        jobs=PreparationJobs(None,None,asyncio.Lock(),root=tmp_path,runner=runner)
        await jobs.start(27205);await jobs.task
        result=jobs.status(27205).job
        assert result.state=='interrupted' and 'Private' not in result.message
        await jobs.close()
    asyncio.run(run())
