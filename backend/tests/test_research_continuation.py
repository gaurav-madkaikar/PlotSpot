import copy

from movie_companion.research_continuation import continue_incomplete_report,frozen_resume_documents,rebase_report,rebase_running_report,refine_review_report


def test_continuation_keeps_productive_records_and_refills_only_missing_purpose(monkeypatch):
    report={'base_collection':None,'state':'incomplete','phase':'finished','stop_reason':'evidence_budget_exhausted',
        'plan':[{'id':'t1','purpose':'story'},{'id':'t2','purpose':'background'},{'id':'t3','purpose':'background'}],
        'records':[{'task_id':'t1'},{'task_id':'t2'},{'task_id':'t3'}],
        'content_coverage':{'facts':{'items':4,'publishers':['a','b']},'quiz':{'items':10,'publishers':['a','b']}},
        'facts':['old-fact'],'questions':['old-question'],'candidates':[]}
    candidates=[{'id':'t1-Q1','ready':True},{'id':'t2-F1','ready':False},{'id':'t3-F1','ready':True}]
    def derive(value,saved):
        assert saved is None
        if value.get('facts')==[]:
            return ['old-fact'],['old-question'],copy.deepcopy(candidates)
        return value['facts'],value['questions'],copy.deepcopy(candidates)
    monkeypatch.setattr('movie_companion.research_continuation.derive',derive)
    result=continue_incomplete_report(report,max_tasks=6)
    assert [task['purpose'] for task in result['plan']]==[
        'story','background','background','background','background','background']
    assert [record['task_id'] for record in result['records']]==['t1','t2']
    assert result['state']=='running' and result['continuation_round']==1
    assert result['facts']==['old-fact'] and result['questions']==['old-question']


def test_continuation_does_not_reuse_excluded_or_operator_rejected_evidence(monkeypatch):
    report={'base_collection':None,'state':'incomplete','phase':'finished',
        'stop_reason':'evidence_budget_exhausted','excluded_source_ids':['excluded'],
        'operator_rejected_task_ids':['t2'],'plan':[
            {'id':'t1','purpose':'background','source_id':'kept'},
            {'id':'t2','purpose':'background','source_id':'rejected'},
            {'id':'t3','purpose':'background','source_id':'excluded'},
            {'id':'t4','purpose':'background','source_id':'usable'}],
        'records':[{'task_id':f't{i}'} for i in range(1,5)],
        'content_coverage':{'facts':{'items':4,'publishers':['a']},
                            'quiz':{'items':10,'publishers':['a','b']}},
        'facts':[],'questions':[],'candidates':[]}
    candidates=[{'id':f't{i}-F1','ready':i==1} for i in range(1,5)]
    monkeypatch.setattr('movie_companion.research_continuation.derive',
        lambda value,saved:([],[],copy.deepcopy(candidates)))

    result=continue_incomplete_report(report,max_tasks=4)

    assert [task['source_id'] for task in result['plan']]==[
        'kept','kept','usable','kept']


def test_rebase_revalidates_checkpoint_before_adopting_current_workflow(monkeypatch):
    report={'state':'running','base_collection':None,'workflow_sha256':'old',
        'facts':['fact'],'questions':['question'],'candidates':['candidate']}
    calls=[]
    def derive(value,saved,check_identity=True):
        calls.append(check_identity)
        if check_identity:assert value['workflow_sha256']=='current'
        return ['fact'],['question'],['candidate']
    monkeypatch.setattr('movie_companion.research_continuation.derive',derive)
    monkeypatch.setattr('movie_companion.research_continuation.workflow_hash',lambda:'current')
    result=rebase_running_report(report)
    assert calls==[False,True]
    assert result['workflow_sha256']=='current'
    assert result['rebased_from_workflow_sha256']=='old'


def test_rebase_accepts_a_completed_review_checkpoint(monkeypatch):
    report={'state':'needs_review','base_collection':None,'workflow_sha256':'old',
        'facts':[],'questions':[],'candidates':[]}
    monkeypatch.setattr('movie_companion.research_continuation.derive',lambda *a,**k:([],[],[]))
    monkeypatch.setattr('movie_companion.research_continuation.workflow_hash',lambda:'current')
    assert rebase_report(report)['state']=='needs_review'


def test_frozen_resume_reuses_checkpoint_sources_without_live_acquisition(monkeypatch):
    source=type('Source',(),{})()
    monkeypatch.setattr('movie_companion.research_checkpoint.source_map',lambda movie_id,raw:{'s':source})
    report={'state':'running','movie_id':13,'sources':[{'frozen':True}],
        'research':{'policy':'original-trace','sources':1}}
    documents,trace=frozen_resume_documents(report,13)
    assert documents[0].source is source
    assert trace==report['research'] and trace is not report['research']


def test_review_refinement_keeps_rejected_audit_record_and_refills_missing_purpose(monkeypatch):
    report={'base_collection':None,'state':'needs_review','phase':'finished','stop_reason':'targets_reached',
        'movie_id':13,'sources':[],'plan':[{'id':'t1','purpose':'story','source_id':'story'},
        {'id':'t2','purpose':'background','source_id':'bad'},{'id':'t3','purpose':'background','source_id':'good'}],
        'records':[{'task_id':'t1'},{'task_id':'t2'},{'task_id':'t3'}],
        'facts':['bad','good'],'questions':['question'],'candidates':[]}
    def derive(value,saved):
        cs=[]
        for task in value['plan'][:len(value['records'])]:
            kind='Q1' if task['purpose']=='story' else 'F1'
            cs.append({'id':task['id']+'-'+kind,'ready':True})
        return [c for c in cs if c['id'].endswith('F1')],[c for c in cs if c['id'].endswith('Q1')],cs
    monkeypatch.setattr('movie_companion.research_continuation.derive',derive)
    monkeypatch.setattr('movie_companion.research_continuation._coverage',lambda r,s:{
        'facts':{'items':4,'publishers':['a','b']},'quiz':{'items':10,'publishers':['a','b']},'complete':False})
    result=refine_review_report(report,rejections={'t2':'Wrong film version.'},
        excluded_source_ids=('bad',),max_tasks=5)
    assert result['state']=='running' and result['refinement_of']
    assert result['operator_rejected_task_ids']==['t2']
    assert [record['task_id'] for record in result['records']]==['t1','t2','t3']
    assert [task['source_id'] for task in result['plan'][3:]]==['good','good']


def test_review_refinement_keeps_but_never_reuses_rejected_evidence_task(monkeypatch):
    report={'base_collection':None,'state':'needs_review','phase':'finished','stop_reason':'targets_reached',
        'movie_id':13,'sources':[],'plan':[
            {'id':'t1','purpose':'background','source_id':'shared','evidence':['rejected']},
            {'id':'t2','purpose':'background','source_id':'shared','evidence':['alternative']}],
        'records':[{'task_id':'t1'},{'task_id':'t2'}],
        'facts':['bad','good'],'questions':[],'candidates':[]}
    def derive(value,saved):
        candidates=[{'id':task['id']+'-F1','ready':True}
                    for task in value['plan'][:len(value['records'])]]
        return candidates,[],candidates
    monkeypatch.setattr('movie_companion.research_continuation.derive',derive)
    monkeypatch.setattr('movie_companion.research_continuation._coverage',lambda r,s:{
        'facts':{'items':4,'publishers':['a','b']},'quiz':{'items':10,'publishers':['a','b']},'complete':False})

    result=refine_review_report(report,rejections={'t1':'Malformed wording.'},max_tasks=4)

    assert result['state']=='running'
    assert result['operator_rejected_task_ids']==['t1']
    assert result['plan'][0]['evidence']==['rejected']
    assert {tuple(task['evidence']) for task in result['plan'][2:]}=={('alternative',)}
