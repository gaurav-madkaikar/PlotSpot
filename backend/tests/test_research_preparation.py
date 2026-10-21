import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from movie_companion import research_preparation as pipeline
from movie_companion.content_evidence_retrieval import RetrievedEvidence
from movie_companion.content_proposal_review import DraftReview
from movie_companion.content_proposals import ContentProposals, EvidenceOrigin, ProposalEvidence
from movie_companion.movie_research import research_movie, ResearchLoad
from movie_companion.proposal_evidence import evidence_batches
from test_movie_research import story_document, background_document, good_story, good_background


def install_story(monkeypatch,events):
    async def verify(*args):events.append('verify')
    async def retrieve(*args,source,**kwargs):
        events.append('story_retrieve')
        return RetrievedEvidence(evidence_batches(source,max_batches=1),{'fixture':True})
    async def propose(*args,evidence,**kwargs):
        events.append('story_generate')
        assert all(p.purpose=='story' for p in evidence)
        return ContentProposals(facts=[],questions=[{
            'question':'What does Louise learn about her apparent memories?',
            'options':['They show the future','They are army simulations','They show another planet','They are dreams'],
            'correct_index':0,'passage_id':evidence[0].passage_id,'evidence_quote':evidence[0].text}])
    async def review(*args,**kwargs):
        events.append('story_review')
        return DraftReview(items=[{'item_id':'Q1','decision':'accept','reason':'The exact source supports this answer.'}])
    async def readiness(*args,base_eligible,**kwargs):
        return {'ready_ids':base_eligible,'items':[],'error_type':None}
    monkeypatch.setattr(pipeline,'verify_local_model',verify)
    monkeypatch.setattr(pipeline,'retrieve_draft_evidence',retrieve)
    monkeypatch.setattr(pipeline,'propose_content',propose)
    monkeypatch.setattr(pipeline,'review_proposals',review)
    monkeypatch.setattr(pipeline,'quiz_readiness',readiness)


def inspect(monkeypatch, background=good_background):
    async def call():
        research=await research_movie(movie_id=329865,story_loader=good_story,background_loader=background)
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await pipeline.inspect_research(client,research=research,store=object(),
                saved={'quiz':SimpleNamespace(items=[])})
    return asyncio.run(call())


def test_joined_research_consumed_in_serial_model_order(monkeypatch):
    events=[];install_story(monkeypatch,events)
    async def background(*args,documents,**kwargs):
        assert events[-1]=='story_review';events.append('background')
        assert documents[0].source.source_id=='time-arrival'
        return {'sources':[{}],'candidates':[],'errors':[]}
    monkeypatch.setattr(pipeline,'inspect_background_sources',background)
    report=inspect(monkeypatch)
    assert events[-4:]==['story_retrieve','story_generate','story_review','background']
    assert report['local_model_concurrency']==1 and report['published'] is False
    assert report['branches'][0]['result']['eligible_for_review']==['Q1']
    assert report['code_changed_during_run'] is False


def test_missing_background_evidence_skips_its_model_calls(monkeypatch):
    events=[];install_story(monkeypatch,events)
    async def empty():return ResearchLoad()
    async def forbidden(*args,**kwargs):raise AssertionError('no evidence')
    monkeypatch.setattr(pipeline,'inspect_background_sources',forbidden)
    report=inspect(monkeypatch,empty)
    assert report['branches'][1]['state']=='unavailable'
    assert report['branches'][0]['state']=='inspected'


def test_failed_story_model_keeps_background_inspection(monkeypatch):
    events=[];install_story(monkeypatch,events)
    async def broken(*args,**kwargs):raise httpx.HTTPError('secret response')
    async def background(*args,**kwargs):return {'sources':[{}],'candidates':[],'errors':[]}
    monkeypatch.setattr(pipeline,'propose_content',broken)
    monkeypatch.setattr(pipeline,'inspect_background_sources',background)
    report=inspect(monkeypatch)
    assert [b['state'] for b in report['branches']]==['failed','inspected']
    assert report['branches'][0]['error_type']=='HTTPError'


def test_revalidate_whole_research_plan_before_any_model_call(monkeypatch):
    async def call():
        research=await research_movie(movie_id=329865,story_loader=good_story,background_loader=good_background)
        bad=replace(background_document().source,movie_id=155)
        branch=replace(research.branches[1],documents=(replace(background_document(),source=bad),))
        research=replace(research,branches=(research.branches[0],branch))
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            with pytest.raises(ValueError):
                await pipeline.inspect_research(client,research=research,store=None,saved=None)
    async def forbidden(*args):raise AssertionError('must validate first')
    monkeypatch.setattr(pipeline,'verify_local_model',forbidden)
    asyncio.run(call())


def test_each_article_keeps_its_own_provenance_and_partial_failure(monkeypatch):
    async def verify(*args):pass
    async def retrieve(client,store,snapshot):
        source=snapshot.source
        if source.source_id=='time-arrival':raise httpx.HTTPError('upstream body')
        section=source.sections[0]
        origin=EvidenceOrigin(movie_id=329865,source_id=source.source_id,source_ref=source.source_ref,
            revision=source.revision,section_title=section.title,section_category=section.category,
            start=0,end=len(source.text))
        return [ProposalEvidence(passage_id='P1',purpose='background',text=source.text,origin=origin)],{}
    async def propose(client,evidence,previous):
        return ContentProposals(facts=[{'title':'A physical chamber',
            'text':'A physical spacecraft chamber was constructed for filming, replacing the need for a green screen.',
            'passage_id':'P1','evidence_quote':evidence[0].text}],questions=[])
    async def review(*args,**kwargs):
        return DraftReview(items=[{'item_id':'F1','decision':'accept','reason':'The evidence supports the practical chamber.'}])
    async def readiness(*args,**kwargs):return {'ready':True}
    monkeypatch.setattr(pipeline,'verify_local_model',verify)
    monkeypatch.setattr(pipeline,'article_evidence',retrieve)
    monkeypatch.setattr(pipeline,'propose_article_facts',propose)
    monkeypatch.setattr(pipeline,'review_facts',review)
    monkeypatch.setattr(pipeline,'fact_readiness',readiness)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await pipeline.inspect_background_sources(client,documents=(background_document(),background_document('bfi-arrival')),
                store=None,saved={'facts':SimpleNamespace(items=[])})
    report=asyncio.run(call())
    assert len(report['errors'])==1 and report['errors'][0]['source_id']=='time-arrival'
    assert len(report['candidates'])==1
    assert report['candidates'][0]['origin']['source_id']=='bfi-arrival'
    assert report['candidates'][0]['eligible_for_review'] is True
    assert report['published'] is False


def test_inspection_cancellation_propagates_without_starting_other_model_branch(monkeypatch):
    async def call():
        entered=asyncio.Event();ended=[]
        async def hung(*args,**kwargs):
            entered.set()
            try:await asyncio.Event().wait()
            finally:ended.append(1)
        monkeypatch.setattr(pipeline,'verify_local_model',hung)
        research=await research_movie(movie_id=329865,story_loader=good_story,background_loader=good_background)
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            task=asyncio.create_task(pipeline.inspect_research(client,research=research,store=None,saved=None))
            await entered.wait();task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
        assert ended==[1]
    asyncio.run(call())
