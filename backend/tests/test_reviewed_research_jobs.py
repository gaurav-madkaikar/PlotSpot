import asyncio,copy,json
from dataclasses import asdict,replace
from pathlib import Path

import httpx,pytest
from fastapi.testclient import TestClient

from movie_companion import research_workflow as flow
from movie_companion.content_store import ContentStore
from movie_companion.structured_content_review import StructuredReview
from movie_companion.content_proposals import ContentProposals,ProposalEvidence,EvidenceOrigin
from movie_companion.content_readiness import POLICY as READINESS
from movie_companion.evidence_store import SourceDocument
from movie_companion.main import app,get_content_store
from movie_companion.movie_research import ResearchDocument
from movie_companion.preparation_jobs import PreparationJobs,project_job
from movie_companion.preparation_job_store import PreparationJobStore
from movie_companion.preparation_routes import get_jobs
from movie_companion.research_checkpoint import derive,digest,validate_resume
from movie_companion.research_jobs import ResearchPreparationJobs
from movie_companion.research_publication import ReviewedSelection,publish_selection
from movie_companion.preparation_resume import ResumeMismatch
from movie_companion.source_sections import SourceSection
from movie_companion.movie_questions import QuestionCitation
from movie_companion.web_corpus_store import WebCorpusStore
from movie_companion.source_coverage import content_coverage
from movie_companion.discussion_support import SupportReview
from test_content_store import fixture_collection


def source_fixture():
    text='Mira finds a brass compass in the lighthouse before dawn.'
    return SourceDocument('wiki-fixture',157336,text,
        'English Wikipedia contributors: Interstellar (film)',
        'https://en.wikipedia.org/w/index.php?oldid=123','enwiki-123-sections-v3-body',
        sections=(SourceSection(0,len(text),'Plot','plot'),))


def seed_bank(tmp_path):
    source,(quiz,facts)=fixture_collection();bank=ContentStore(tmp_path/'content.db')
    bank.publish(157336,version='curated',source_revision=source.revision,quiz=quiz,facts=facts)
    return bank


def install_pipeline(monkeypatch,*,tasks=1,cancel_second=False,calls=None,source=None,proposal=None,
                     support_verdict='supported',direct=None):
    calls=[] if calls is None else calls
    evidence_source=source or source_fixture()
    async def verify(*args):pass
    async def plan(*args,**kwargs):
        s=evidence_source.sections[0]
        evidence=ProposalEvidence(passage_id='P1',purpose='story',text=evidence_source.text,
            origin=EvidenceOrigin(movie_id=evidence_source.movie_id,source_id=evidence_source.source_id,source_ref=evidence_source.source_ref,
                revision=evidence_source.revision,section_title=s.title,section_category=s.category,start=0,end=len(evidence_source.text)))
        return [{'id':f't{i+1}','purpose':'story','source_id':evidence_source.source_id,'evidence':[evidence.model_dump()]} for i in range(tasks)]
    async def generate(*args,existing_questions,**kwargs):
        calls.append(len(existing_questions))
        if cancel_second and len(calls)==2:raise asyncio.CancelledError
        selected=proposal or {'question':'Where does Mira find the brass compass?',
            'options':['The lighthouse','A cave','A castle','The harbor'],'correct_index':0,
            'passage_id':'P1','evidence_quote':evidence_source.text}
        return ContentProposals(facts=[],questions=[selected])
    async def critic(*args,**kwargs):return StructuredReview(items=[{'item_id':'Q1','decision':'accept','reason':'The complete source supports the location answer.',
        'assessment':{'item_id':'Q1','support':'supported','content':'eligible','supported_option_indices':[0],
                      'plausible_options':True,'narrative_focus':'turning_point',
                      'narrative_significance':'central',
                      'reason':'The complete source supports the location answer.'}}],model_calls=1)
    async def readiness(*args,proposals,quiz,**kwargs):
        from movie_companion.quiz_novelty import deterministic_topic,saved_question_pairs
        p=proposals.questions[0]
        prior=[{'id':f'B{i+1}',**pair} for i,pair in enumerate(saved_question_pairs(quiz))]
        fixed=deterministic_topic({'id':'Q1','question':p.question,'answer':p.options[p.correct_index]},prior)
        view=fixed.record() if fixed else {'candidate_id':'Q1','novelty':'new','matches':[],
            'clarity':'clear','reason':'A new fact.','clarity_reason':'A direct question.'}
        if view['clarity']=='not_reviewed':view['clarity']='clear'
        view['ready']=view['novelty']=='new' and view['clarity']=='clear'
        return {'policy':READINESS,'ready_ids':['Q1'] if view['ready'] else [],'items':[view],'error_type':None}
    async def support(*args,quotes,**kwargs):
        return SupportReview(support_verdict,'The independent answer check reviewed the exact source sentence.',
            quotes[0] if support_verdict=='supported' else 'Insufficient evidence.',
            (quotes[0],) if support_verdict=='supported' else ())
    async def saved_corroboration(*args,**kwargs):return direct
    monkeypatch.setattr(flow,'verify_local_model',verify);monkeypatch.setattr(flow,'build_plan',plan)
    monkeypatch.setattr(flow,'generate_batch',generate);monkeypatch.setattr(flow,'review_questions',critic)
    monkeypatch.setattr(flow,'quiz_readiness',readiness)
    monkeypatch.setattr(flow,'review_support',support)
    monkeypatch.setattr(flow,'corroborate_saved_question',saved_corroboration)
    return calls


def prepare(monkeypatch,tmp_path,*,tasks=1):
    bank=seed_bank(tmp_path);calls=install_pipeline(monkeypatch,tasks=tasks)
    saved=bank.load(157336)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,documents=[ResearchDocument(source_fixture())],
                store=None,saved=saved,refresh=True)
    report=asyncio.run(run());report['base_collection']={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()}
    return bank,report,calls


def test_workflow_supplies_saved_topics_and_derives_retention(monkeypatch,tmp_path):
    bank,report,calls=prepare(monkeypatch,tmp_path)
    assert calls==[11]  # ten scored questions plus an unscored reflection
    assert report['state']=='needs_review' and len(report['questions'])==1
    assert derive(report,bank.load(157336))[1]==report['questions']
    assert bank.load(157336)['version']=='curated'


def test_question_is_not_retained_when_separate_whole_answer_check_fails(monkeypatch,tmp_path):
    bank=seed_bank(tmp_path);saved=bank.load(157336)
    proposal={'question':'Where does Mira find the brass compass?',
        'options':['At the coastal beacon','A cave','A castle','The harbor'],'correct_index':0,
        'passage_id':'P1','evidence_quote':source_fixture().text}
    install_pipeline(monkeypatch,proposal=proposal,support_verdict='unsupported')
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,
                documents=[ResearchDocument(source_fixture())],store=None,saved=saved,refresh=True)
    report=asyncio.run(run())
    assert report['questions']==[]
    assert report['candidates'][0]['ready'] is False


def test_rejected_draft_does_not_reserve_its_topic_for_later_sources():
    report={'candidates':[{'kind':'question','ready':False,'proposal':{
        'question':'Which place does Mira visit?','options':['A','B','C','D'],'correct_index':0}},
        {'kind':'fact','ready':True,'proposal':{'text':'The set used a practical lighthouse model.'}}]}
    pairs,facts=flow.saved_context(None,report)
    assert pairs==[] and facts==['The set used a practical lighthouse model.']


def test_new_bank_background_plan_alternates_wikipedia_depth_and_independent_sources():
    tasks=[*({'source_id':'enwiki-1','slot':i} for i in range(8)),
           *({'source_id':f'web-{i}','slot':i} for i in range(12))]
    selected=flow.prioritized_new_background(tasks)
    assert len(selected)==15
    assert [task['source_id'] for task in selected[:6]]==[
        'enwiki-1','web-0','enwiki-1','web-1','enwiki-1','web-2']
    assert sum(task['source_id']=='enwiki-1' for task in selected)==5
    assert len({task['source_id'] for task in selected if task['source_id'].startswith('web-')})==10


def test_new_bank_reserves_last_slot_for_a_second_publisher():
    from movie_companion.research_checkpoint import final_slot_allows_publisher
    retained=[{'origin':{'source_ref':'https://en.wikipedia.org/a'}} for _ in range(4)]
    assert not final_slot_allows_publisher(retained,source_ref='https://en.wikipedia.org/b',target=5,enforce=True)
    assert final_slot_allows_publisher(retained,source_ref='https://variety.com/c',target=5,enforce=True)
    assert final_slot_allows_publisher(retained[:3],source_ref='https://en.wikipedia.org/b',target=5,enforce=True)
    assert final_slot_allows_publisher(retained,source_ref='https://en.wikipedia.org/b',target=5,enforce=False)


def test_saved_answer_gate_does_not_read_quiz_state_from_background_record(monkeypatch,tmp_path):
    bank,report,_=prepare(monkeypatch,tmp_path)
    text='A miniature lighthouse set was constructed for the production.'
    source=SourceDocument('wiki-background',157336,text,
        'English Wikipedia contributors: Interstellar (film)',
        'https://en.wikipedia.org/w/index.php?oldid=124','enwiki-124-sections-v3-body',
        sections=(SourceSection(0,len(text),'Production','production'),))
    report['sources'].append(asdict(source));report['sources_sha256']=digest(report['sources'])
    evidence=ProposalEvidence(passage_id='P2',purpose='background',text=text,
        origin=EvidenceOrigin(movie_id=157336,source_id=source.source_id,source_ref=source.source_ref,
            revision=source.revision,section_title='Production',section_category='production',start=0,end=len(text)))
    report['plan'].append({'id':'t2','purpose':'background','source_id':source.source_id,
        'evidence':[evidence.model_dump()]})
    report['records'].append({'task_id':'t2','proposals':{'facts':[],'questions':[]},
        'review':{'items':[]},'checks':[],'fact_readiness':{},'quiz_readiness':None,
        'answer_support':{},'saved_answer_support':{},'saved_corroboration':None})
    facts,questions,candidates=derive(report,bank.load(157336))
    assert facts==report['facts'] and questions==report['questions']
    assert candidates==report['candidates']


def test_strict_workflow_stays_incomplete_until_each_bank_has_two_publishers(monkeypatch,tmp_path):
    bank=seed_bank(tmp_path);saved=bank.load(157336);install_pipeline(monkeypatch)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,
                documents=[ResearchDocument(source_fixture())],store=None,saved=saved,refresh=True,
                require_diverse_sources=True)
    report=asyncio.run(run())
    assert report['targets']=={'facts':1,'questions':1}
    assert report['facts']==[] and report['questions']==[]
    assert report['state']=='incomplete'
    assert report['content_coverage']['complete'] is False
    assert report['content_coverage']['facts']['publishers']==['wikipedia.org']
    assert report['content_coverage']['quiz']['publishers']==['wikipedia.org']


def test_strict_publication_rejects_candidate_from_existing_publisher(monkeypatch,tmp_path):
    bank=seed_bank(tmp_path);saved=bank.load(157336);install_pipeline(monkeypatch)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,
                documents=[ResearchDocument(source_fixture())],store=None,saved=saved,refresh=True,
                require_diverse_sources=True)
    report=asyncio.run(run());report['base_collection']={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()}
    jobs,record=queued_terminal(tmp_path,report)
    sources=tmp_path/'sources';sources.mkdir();(sources/'157336.json').write_text(json.dumps(asdict(source_fixture())))
    before=bank.load(157336)
    with pytest.raises(ValueError,match='Only validated retained candidates'):
        publish_selection(jobs=jobs,bank=bank,selection=selection(record),sources=sources)
    assert bank.load(157336)==before and bank.receipt(record['id']) is None


def test_strict_enrichment_directly_corroborates_saved_question_before_generation(monkeypatch,tmp_path):
    monkeypatch.setenv('PLOTSPOT_WEB_CORPUS_DB',str(tmp_path/'web.db'))
    bank=seed_bank(tmp_path);saved=bank.load(157336)
    target=next(item for item in saved['quiz'].items if item.kind!='interpretation')
    answer=target.options[target.correct_index]
    text=f'The released story states that {answer} is the outcome asked about in this question.'
    source=SourceDocument('tmdb-157336',157336,text,'The Movie Database (TMDB) · Interstellar',
        'https://www.themoviedb.org/movie/157336','tmdb-details-'+'b'*64+'-v1','unknown',
        (SourceSection(0,len(text),'Overview','plot'),))
    WebCorpusStore().remember(source,'provider')
    from movie_companion.saved_quiz_corroboration import POLICY as SAVED_CORROBORATION
    direct={'policy':SAVED_CORROBORATION,'target_id':target.id,'question':target.question,
        'options':target.options,'correct_index':target.correct_index,'passage_id':'P1',
        'evidence_quote':text,'origin':EvidenceOrigin(movie_id=157336,source_id=source.source_id,
            source_ref=source.source_ref,revision=source.revision,section_title='Overview',
            section_category='plot',start=0,end=len(text)).model_dump(),
        'review':{'verdict':'supported','reason':'The sentence answers the exact saved question.',
            'evidence_answer':answer,'evidence_quotes':[text]}}
    calls=install_pipeline(monkeypatch,source=source,direct=direct)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,
                documents=[ResearchDocument(source)],store=None,saved=saved,refresh=True,
                require_diverse_sources=True)
    report=asyncio.run(run())
    assert calls==[] and len(report['questions'])==1
    assert report['questions'][0]['corroborates']==target.id
    assert derive(report,saved)[1]==report['questions']


def test_strict_publication_can_add_independent_citation_to_duplicate_saved_question(monkeypatch,tmp_path):
    monkeypatch.setenv('PLOTSPOT_WEB_CORPUS_DB',str(tmp_path/'web.db'))
    _,(quiz,facts)=fixture_collection();saved_question=quiz.items[0]
    answer=saved_question.options[saved_question.correct_index]
    text=f'{answer} is the answer to the saved story question in this authored TMDB fixture.'
    provider=SourceDocument('tmdb-157336',157336,text,'The Movie Database (TMDB) · Interstellar',
        'https://www.themoviedb.org/movie/157336','tmdb-details-'+'a'*64+'-v1','unknown',
        (SourceSection(0,len(text),'Overview','plot'),))
    WebCorpusStore().remember(provider,'provider')
    provider_citation=QuestionCitation(passage_id='provider-fact',source_label=provider.source_label,
        source_ref=provider.source_ref,revision=provider.revision,excerpt=text)
    facts.items[0]=facts.items[0].model_copy(update={'citations':[facts.items[0].citations[0],provider_citation]})
    bank=ContentStore(tmp_path/'content.db')
    manifest={c.revision:c.source_ref for item in [*quiz.items,*facts.items] for c in item.citations}
    bank.publish(157336,version='curated',source_revision=quiz.items[0].citations[0].revision,
        quiz=quiz,facts=facts,source_manifest=manifest)
    saved=bank.load(157336)
    proposal={'question':saved_question.question,'options':saved_question.options,
        'correct_index':saved_question.correct_index,'passage_id':'P1','evidence_quote':text}
    install_pipeline(monkeypatch,source=provider,proposal=proposal)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,
                documents=[ResearchDocument(provider)],store=None,saved=saved,refresh=True,
                require_diverse_sources=True)
    report=asyncio.run(run());assert report['questions'],report
    candidate=report['questions'][0]
    assert candidate['corroborates']==saved_question.id and report['state']=='needs_review'
    report['base_collection']={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()}
    jobs,record=queued_terminal(tmp_path,report)
    publish_selection(jobs=jobs,bank=bank,selection=selection(record,[candidate['id']]),sources=tmp_path/'sources')
    updated=bank.load(157336)
    assert len(updated['quiz'].items)==len(saved['quiz'].items)
    assert provider.source_ref in {citation.source_ref for citation in updated['quiz'].items[0].citations}
    assert content_coverage(updated['quiz'],updated['facts'])['complete'] is True


def test_cancel_checkpoint_resumes_without_repeating_completed_call(monkeypatch,tmp_path):
    bank=seed_bank(tmp_path);saved=bank.load(157336);calls=[];checkpoints=[]
    install_pipeline(monkeypatch,tasks=2,cancel_second=True,calls=calls)
    async def first():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            with pytest.raises(asyncio.CancelledError):
                await flow.prepare_research(client,movie_id=157336,documents=[ResearchDocument(source_fixture())],store=None,saved=saved,refresh=True,checkpoint=lambda r:checkpoints.append(copy.deepcopy(r)))
    asyncio.run(first());resume=checkpoints[-1]
    assert len(resume['records'])==1 and len(resume['questions'])==1
    install_pipeline(monkeypatch,tasks=2,calls=calls)
    async def second():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await flow.prepare_research(client,movie_id=157336,documents=[ResearchDocument(source_fixture())],store=None,saved=saved,refresh=True,resume=resume)
    result=asyncio.run(second())
    assert len(calls)==3 and len(result['records'])==2
    assert len(result['questions'])==1  # exact duplicate from task two is not retained


@pytest.mark.parametrize('tamper',['ready','selection','source','policy','bank'])
def test_resume_rejects_tampering_before_inference(monkeypatch,tmp_path,tamper):
    bank,report,_=prepare(monkeypatch,tmp_path);bad=copy.deepcopy(report)
    if tamper=='ready':bad['records'][0]['quiz_readiness']['items'][0]['ready']=False
    if tamper=='selection':bad['questions']=[]
    if tamper=='source':bad['sources'][0]['text']='A replaced source sentence with different evidence.'
    if tamper=='policy':bad['workflow_sha256']='0'*64
    if tamper=='bank':bad['bank_sha256']='0'*64
    with pytest.raises(ResumeMismatch):validate_resume(bad,bank.load(157336),[source_fixture()])


def queued_terminal(tmp_path,report):
    jobs=PreparationJobStore(tmp_path/'jobs.db',validate=PreparationJobs._validate)
    record={'id':'a'*32,'movie_id':157336,'state':'queued','phase':'source','updated_at':'2026-10-12T00:00:00Z','message':'Waiting.','report':None,'refresh':True}
    jobs.enqueue(record);assert jobs.leader('worker');record=jobs.claim('worker')
    record.update(state=report['state'],phase='finished',report=report,message='Ready for review.')
    jobs.save(record,'worker')
    return jobs,record


def selection(record,ids=None):
    return {'movie_id':157336,'job_id':record['id'],'report_sha256':digest(record['report']),
        'item_ids':ids or ['t1-Q1'],'reviewer':'Unit-test operator','review_kind':'human_source_review',
        'reviewed_sources_and_novelty':True}


def test_reviewed_publication_commits_receipt_and_retry_is_idempotent(monkeypatch,tmp_path):
    bank,report,_=prepare(monkeypatch,tmp_path);jobs,record=queued_terminal(tmp_path,report)
    sources=tmp_path/'sources';sources.mkdir();(sources/'157336.json').write_text(json.dumps(asdict(source_fixture())))
    reviewed=selection(record);before=bank.load(157336)
    first=publish_selection(jobs=jobs,bank=bank,selection=reviewed,sources=sources)
    after=bank.load(157336)
    assert len(after['quiz'].items)==len(before['quiz'].items)+1
    assert after['facts']==before['facts'] and jobs.latest(157336)['state']=='published'
    assert project_job(jobs.latest(157336)).publication_approved is True
    second=publish_selection(jobs=jobs,bank=bank,selection=reviewed,sources=sources)
    assert second['replayed'] is True and bank.load(157336)==after
    assert bank.receipt(record['id'])['report_sha256']==reviewed['report_sha256']


@pytest.mark.parametrize('failure',['unknown-id','report','source','stale-bank','not-reviewed','different-movie'])
def test_failed_selection_keeps_last_collection(monkeypatch,tmp_path,failure):
    bank,report,_=prepare(monkeypatch,tmp_path);jobs,record=queued_terminal(tmp_path,report)
    sources=tmp_path/'sources';sources.mkdir();(sources/'157336.json').write_text(json.dumps(asdict(source_fixture())))
    reviewed=selection(record)
    if failure=='unknown-id':reviewed['item_ids']=['t1-Q2']
    if failure=='report':reviewed['report_sha256']='0'*64
    if failure=='source':(sources/'157336.json').write_text(json.dumps(asdict(replace(source_fixture(),text='Mira finds a brass compass beside the harbor before dawn.'))))
    if failure=='not-reviewed':reviewed['reviewed_sources_and_novelty']=False
    if failure=='different-movie':reviewed['movie_id']=329865
    if failure=='stale-bank':
        saved=bank.load(157336);bank.publish(157336,version='another refresh',source_revision=saved['source_revision'],quiz=saved['quiz'],facts=saved['facts'],source_manifest=saved['source_manifest'])
    before=bank.load(157336)
    with pytest.raises(ValueError):publish_selection(jobs=jobs,bank=bank,selection=reviewed,sources=sources)
    assert bank.load(157336)==before and bank.receipt(record['id']) is None


def test_reuse_job_makes_no_source_or_model_calls_and_routes_refresh(content_member, monkeypatch,tmp_path):
    bank=seed_bank(tmp_path)
    async def run():
        jobs=ResearchPreparationJobs(None,None,asyncio.Lock(),root=tmp_path/'queue',bank_store=bank,poll_seconds=.01)
        await jobs.start(157336)
        for _ in range(100):
            if jobs.status(157336).job.state=='ready':break
            await asyncio.sleep(.01)
        assert jobs.status(157336).job.state=='ready'
        assert jobs.store.latest(157336)['report']['reused'] is True
        await jobs.close()
    asyncio.run(run())
    class Fake:
        def __init__(self):self.refresh=None
        async def start(self,movie_id,*,refresh=False):
            self.refresh=refresh
            from movie_companion.preparation_jobs import DraftStatus
            return DraftStatus(available=True)
    fake=Fake();app.dependency_overrides[get_jobs]=lambda:fake
    try:
        client=content_member()
        assert client.post('/api/movies/157336/preparation',json={'allow_spoilers':True,'refresh':True}).status_code==202
        assert fake.refresh is True
        assert client.post('/api/movies/157336/preparation',json={'allow_spoilers':True,'refresh':'yes'}).status_code==422
    finally:app.dependency_overrides.pop(get_jobs,None)


def review_setup(monkeypatch,tmp_path):
    bank,report,_=prepare(monkeypatch,tmp_path);jobs,record=queued_terminal(tmp_path,report)
    sources=tmp_path/'sources';sources.mkdir();(sources/'157336.json').write_text(json.dumps(asdict(source_fixture())))
    return bank,jobs,record,sources


def test_contradictory_critic_assessment_cannot_resume(monkeypatch,tmp_path):
    bank,report,_=prepare(monkeypatch,tmp_path)
    report['records'][0]['review']['items'][0]['assessment'].update(
        support='contradicted_or_exceeds',supported_option_indices=[1])
    with pytest.raises(ResumeMismatch):validate_resume(report,bank.load(157336),[source_fixture()])


def test_publication_transaction_rolls_back_if_receipt_insert_fails(monkeypatch,tmp_path):
    import sqlite3
    bank,jobs,record,sources=review_setup(monkeypatch,tmp_path);before=bank.load(157336)
    with bank._connect() as db:
        db.execute("CREATE TRIGGER deny_receipt BEFORE INSERT ON publication_receipts BEGIN SELECT RAISE(ABORT,'receipt failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        publish_selection(jobs=jobs,bank=bank,selection=selection(record),sources=sources)
    assert bank.load(157336)==before and bank.receipt(record['id']) is None
    assert jobs.latest(157336)['state']=='needs_review'


def test_crash_after_bank_commit_reconciles_on_retry(monkeypatch,tmp_path):
    bank,jobs,record,sources=review_setup(monkeypatch,tmp_path);reviewed=selection(record)
    original=jobs.mark_published
    def crash(*args):raise OSError('Simulated process crash after content commit')
    monkeypatch.setattr(jobs,'mark_published',crash)
    with pytest.raises(OSError):publish_selection(jobs=jobs,bank=bank,selection=reviewed,sources=sources)
    committed=bank.load(157336);assert bank.receipt(record['id']) is not None
    assert jobs.latest(157336)['state']=='needs_review'
    monkeypatch.setattr(jobs,'mark_published',original)
    assert publish_selection(jobs=jobs,bank=bank,selection=reviewed,sources=sources)['replayed'] is True
    assert bank.load(157336)==committed and jobs.latest(157336)['state']=='published'
    conflict={**reviewed,'reviewer':'Different selection operator'}
    with pytest.raises(ValueError,match='conflicts'):
        publish_selection(jobs=jobs,bank=bank,selection=conflict,sources=sources)


def test_publication_cas_rejects_refresh_between_validation_and_commit(monkeypatch,tmp_path):
    bank,jobs,record,sources=review_setup(monkeypatch,tmp_path);original=bank.publish_with_receipt
    changed=[]
    def concurrent_refresh(*args,**kwargs):
        saved=bank.load(157336)
        bank.publish(157336,version='concurrent refresh',source_revision=saved['source_revision'],
            quiz=saved['quiz'],facts=saved['facts'],source_manifest=saved['source_manifest'])
        changed.append(bank.load(157336));return original(*args,**kwargs)
    monkeypatch.setattr(bank,'publish_with_receipt',concurrent_refresh)
    with pytest.raises(ValueError,match='changed before'):
        publish_selection(jobs=jobs,bank=bank,selection=selection(record),sources=sources)
    assert bank.load(157336)==changed[0] and bank.receipt(record['id']) is None


def test_selected_new_bank_must_meet_full_quotas(monkeypatch,tmp_path):
    bank=ContentStore(tmp_path/'empty.db');install_pipeline(monkeypatch)
    report=asyncio.run(flow.prepare_research(None,movie_id=157336,documents=[ResearchDocument(source_fixture())],
        store=None,saved=None,refresh=True));report['base_collection']=None
    assert report['state']=='incomplete'
    jobs,record=queued_terminal(tmp_path,report)
    sources=tmp_path/'sources';sources.mkdir();(sources/'157336.json').write_text(json.dumps(asdict(source_fixture())))
    with pytest.raises(ValueError,match='ten scored'):
        publish_selection(jobs=jobs,bank=bank,selection=selection(record),sources=sources)
    assert bank.load(157336) is None and bank.receipt(record['id']) is None


def test_article_branch_survives_wikipedia_http_failure(monkeypatch,tmp_path):
    from movie_companion import research_jobs as module
    from movie_companion.background_articles import load_article
    from movie_companion.movie_research import ResearchLoad
    article=load_article('time-arrival',cache_dir=Path(__file__).parents[2]/'.cache/background-articles')
    async def fail(*args,**kwargs):raise httpx.ConnectError('Wikipedia unavailable')
    async def reader():return ResearchLoad((ResearchDocument(article.source,article),))
    monkeypatch.setattr(module,'fetch_movie_source',fail)
    monkeypatch.setattr(module,'source_loaders',lambda *a,**k:(None,reader))
    async def run():
        jobs=ResearchPreparationJobs(None,None,asyncio.Lock(),root=tmp_path/'queue',sources=tmp_path/'missing')
        docs,trace=await jobs._research_sources(329865)
        assert len(docs)==1 and docs[0].article==article
        assert trace['branches'][0]['status']=='failed' and trace['branches'][1]['status']=='complete'
        await jobs.close()
    asyncio.run(run())


def test_duplicate_refresh_start_keeps_same_queued_job(tmp_path):
    jobs=PreparationJobStore(tmp_path/'jobs.db',validate=PreparationJobs._validate)
    first={'id':'a'*32,'movie_id':157336,'state':'queued','phase':'source','updated_at':'2026-10-12T00:00:00Z',
        'message':'Waiting.','report':None,'refresh':True}
    jobs.enqueue(first)
    assert jobs.enqueue({**first,'id':'b'*32,'refresh':False})==first


def test_research_worker_restarts_from_completed_task(monkeypatch,tmp_path):
    from movie_companion.movie_research import ResearchLoad
    bank=seed_bank(tmp_path);calls=install_pipeline(monkeypatch,tasks=2);entered=asyncio.Event()
    original=flow.generate_batch
    async def slow(*args,**kwargs):
        if len(calls)==1:
            entered.set();await asyncio.Event().wait()
        return await original(*args,**kwargs)
    monkeypatch.setattr(flow,'generate_batch',slow)
    async def sources(self,movie_id):return [ResearchDocument(source_fixture())],{'test':True}
    monkeypatch.setattr(ResearchPreparationJobs,'_research_sources',sources)
    async def run():
        options={'root':tmp_path/'queue','bank_store':bank,'evidence_path':tmp_path/'evidence','poll_seconds':.01}
        first=ResearchPreparationJobs(None,None,asyncio.Lock(),**options)
        started=await first.start(157336,refresh=True);await asyncio.wait_for(entered.wait(),2)
        job_id=started.job.id;await first.close()
        assert first.store.latest(157336)['state']=='queued'
        assert len(first.store.latest(157336)['report']['records'])==1
        monkeypatch.setattr(flow,'generate_batch',original)
        second=ResearchPreparationJobs(None,None,asyncio.Lock(),**options);await second.open()
        for _ in range(200):
            status=second.status(157336).job
            if status.state=='needs_review':break
            await asyncio.sleep(.01)
        assert status.id==job_id and status.state=='needs_review' and status.batches_completed==2
        assert calls==[11,12] and status.questions_retained==1
        await second.close()
    asyncio.run(run())


def test_source_loading_consumes_whole_workflow_budget(monkeypatch,tmp_path):
    from movie_companion import research_jobs as module
    remaining=[]
    async def sources(self,movie_id):await asyncio.sleep(.02);return [],{}
    async def prepare(*args,deadline_seconds,**kwargs):remaining.append(deadline_seconds);return {}
    monkeypatch.setattr(ResearchPreparationJobs,'_research_sources',sources)
    monkeypatch.setattr(module,'prepare_research',prepare)
    async def run():
        jobs=ResearchPreparationJobs(None,None,asyncio.Lock(),root=tmp_path/'queue',bank_store=seed_bank(tmp_path),evidence_path=tmp_path/'evidence')
        jobs.active={'refresh':True};await jobs._prepare(157336,lambda r:None)
        jobs.active=None;await jobs.close()
    asyncio.run(run());assert 599<remaining[0]<599.99
