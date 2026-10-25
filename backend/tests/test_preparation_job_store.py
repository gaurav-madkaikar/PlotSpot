from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import json

import pytest

from movie_companion.preparation_job_store import PreparationJobStore,LeaseLost
from movie_companion.preparation_jobs import PreparationJobs,atomic_json


def record(movie_id=27205,job_id='a'*32):
    return {'id':job_id,'movie_id':movie_id,'state':'queued','phase':'source',
            'updated_at':'2026-10-11T00:00:00Z','message':'Waiting for preparation.','report':None}


def stores(tmp_path):
    clock=[0.0]
    options={'validate':PreparationJobs._validate,'clock':lambda:clock[0],'lease_seconds':30}
    return PreparationJobStore(tmp_path/'jobs.db',**options),PreparationJobStore(tmp_path/'jobs.db',**options),clock


def test_concurrent_enqueue_has_one_logical_job(tmp_path):
    a,b,_=stores(tmp_path)
    def enqueue(i):return (a if i%2 else b).enqueue(record(job_id=f'{i:032x}'))['id']
    with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(enqueue,range(20)))
    assert len(set(ids))==1
    with a.connection() as db:assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==1


def test_fifo_and_exclusive_worker_across_connections(tmp_path):
    a,b,_=stores(tmp_path)
    a.enqueue(record());a.enqueue(record(603,'b'*32))
    assert a.leader('one') and not b.leader('two')
    first=a.claim('one');assert first['movie_id']==27205
    assert a.claim('one') is None
    with pytest.raises(LeaseLost):b.claim('two')
    first.update(state='incomplete',phase='finished')
    a.save(first,'one')
    assert a.claim('one')['movie_id']==603


def test_expired_attempt_recovers_and_old_worker_is_fenced(tmp_path):
    a,b,clock=stores(tmp_path)
    a.enqueue(record());a.leader('one');first=a.claim('one')
    first['report']={'facts':[],'questions':[],'batches':[]}
    a.save(first,'one')
    clock[0]=31
    assert not a.heartbeat('one')
    assert b.leader('two');b.recover('two')
    assert b.latest(27205)['state']=='queued'
    resumed=b.claim('two')
    assert resumed['id']==first['id'] and resumed['report']==first['report']
    with pytest.raises(LeaseLost):a.save(first,'one')
    a.release('one')
    assert b.heartbeat('two')


def test_three_attempts_bound_restart_recovery_and_explicit_retry_gets_new_id(tmp_path):
    a,_,clock=stores(tmp_path);a.enqueue(record())
    for attempt in range(3):
        owner=str(attempt);assert a.leader(owner)
        a.recover(owner)
        assert a.claim(owner)['id']=='a'*32
        clock[0]+=31
    assert a.leader('last');a.recover('last')
    assert a.latest(27205)['state']=='interrupted' and a.claim('last') is None
    assert a.enqueue(record(job_id='b'*32))['id']=='b'*32


def test_explicit_requeue_preserves_a_validated_running_checkpoint(tmp_path):
    a,_,_=stores(tmp_path);r=record();a.enqueue(r);a.leader('one');r=a.claim('one')
    r['report']={'facts':[],'questions':[],'batches':[],'state':'running','phase':'reviewing'}
    r.update(state='failed',phase='finished');a.save(r,'one')
    retried=a.requeue(27205)
    assert retried['id']=='a'*32 and retried['state']=='queued'
    assert retried['report']['state']=='running'
    with a.connection() as db:
        row=db.execute('SELECT attempts,owner,expires FROM jobs').fetchone()
        assert tuple(row)==(0,None,None)


def test_requeue_rejects_terminal_checkpoint_that_cannot_resume(tmp_path):
    a,_,_=stores(tmp_path);r=record();a.enqueue(r);a.leader('one');r=a.claim('one')
    r['report']={'facts':[],'questions':[],'batches':[],'state':'incomplete','phase':'finished'}
    r.update(state='incomplete',phase='finished');a.save(r,'one')
    with pytest.raises(ValueError,match='resumable running checkpoint'):
        a.requeue(27205)


def test_completed_review_can_only_requeue_with_matching_refinement_digest(tmp_path):
    import hashlib
    a,_,_=stores(tmp_path);r=record();a.enqueue(r);a.leader('one');r=a.claim('one')
    previous={'facts':[],'questions':[],'batches':[],'state':'needs_review','phase':'finished'}
    r['report']=previous;r.update(state='needs_review',phase='finished');a.save(r,'one')
    refined={**previous,'state':'running','phase':'reviewing','refinement_of':
        hashlib.sha256(json.dumps(previous,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    assert a.requeue(27205,report=refined)['state']=='queued'


def test_completed_refinement_can_replace_review_without_queueing(tmp_path):
    import hashlib
    a,_,_=stores(tmp_path);r=record();a.enqueue(r);a.leader('one');r=a.claim('one')
    previous={'facts':[],'questions':[],'batches':[],'state':'needs_review','phase':'finished'}
    r['report']=previous;r.update(state='needs_review',phase='finished');a.save(r,'one')
    refined={**previous,'refinement_of':
        hashlib.sha256(json.dumps(previous,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    result=a.replace_review(27205,report=refined)
    assert result['state']=='needs_review' and result['report']==refined


def test_cancellation_blocks_success_and_expired_cancel_never_requeues(tmp_path):
    a,b,clock=stores(tmp_path);a.enqueue(record());a.leader('one');r=a.claim('one')
    b.cancel(27205,r['id'])
    r.update(state='needs_review',phase='finished')
    with pytest.raises(LeaseLost):a.save(r,'one')
    clock[0]=31;b.leader('two');b.recover('two')
    assert b.latest(27205)['state']=='cancelled'
    assert b.claim('two') is None


def test_queued_cancel_and_wrong_id_cannot_cancel_another_job(tmp_path):
    a,_,_=stores(tmp_path);a.enqueue(record())
    with pytest.raises(ValueError):a.cancel(27205,'b'*32)
    assert a.latest(27205)['state']=='queued'
    assert a.cancel(27205,'a'*32)['state']=='cancelled'
    with pytest.raises(ValueError):a.cancel(27205,'a'*32)


def test_legacy_migration_is_once_and_cannot_replace_existing_jobs(tmp_path):
    a,_,_=stores(tmp_path)
    legacy=record();legacy['state']='running'
    atomic_json(tmp_path/'27205.json',legacy)
    atomic_json(tmp_path/'603.json',{**record(603,'b'*32),'state':'failed'})
    atomic_json(tmp_path/'999.json',record(999,'c'*32))
    (tmp_path/'broken.json').write_text('{')
    a.migrate(tmp_path)
    assert a.latest(27205)['state']=='interrupted' and a.latest(603)['state']=='failed'
    assert a.latest(999) is None
    a.enqueue(record(job_id='d'*32));a.migrate(tmp_path)
    assert a.latest(27205)['id']=='d'*32
    assert json.loads((tmp_path/'27205.json').read_text())['state']=='running'


@pytest.mark.parametrize('field,value',[('movie_id',603),('id','c'*32),('state','failed')])
def test_row_payload_identity_tampering_fails_closed(tmp_path,field,value):
    a,_,_=stores(tmp_path);r=record();a.enqueue(r);r[field]=value
    with a.connection() as db:db.execute('UPDATE jobs SET payload=?',(json.dumps(r),))
    with pytest.raises(ValueError):a.latest(27205)


def test_expired_job_cannot_be_revived_by_a_still_valid_worker_heartbeat(tmp_path):
    a,_,clock=stores(tmp_path);a.enqueue(record());a.leader('one');r=a.claim('one')
    with a.connection() as db:db.execute('UPDATE jobs SET expires=1')
    clock[0]=2
    assert not a.heartbeat('one')
    with pytest.raises(LeaseLost):a.save(r,'one')
