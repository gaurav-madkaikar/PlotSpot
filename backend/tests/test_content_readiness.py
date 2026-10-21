import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from movie_companion import content_readiness as module
from movie_companion.content_proposals import ContentProposals,FactProposal,EvidenceOrigin,ProposalEvidence
from movie_companion.discussion_support import SupportReview
from movie_companion.quiz_novelty import NoveltyReview
from test_movie_research import background_document


def fixture(title='A physical chamber',text='A physical chamber replaced the need for a green screen.'):
    source=background_document().source
    section=source.sections[0]
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=source.text,
        origin=EvidenceOrigin(movie_id=source.movie_id,source_id=source.source_id,
            source_ref=source.source_ref,revision=source.revision,section_title=section.title,
            section_category=section.category,start=0,end=len(source.text)))]
    proposal=FactProposal(title=title,text=text,passage_id='P1',evidence_quote=source.text)
    return source,evidence,proposal


def run_fact(monkeypatch,*,verdict='supported',title='A physical chamber',
             text='A physical chamber replaced the need for a green screen.',base=True,error=None):
    source,evidence,proposal=fixture(title,text)
    async def review(*args,quotes,answer,**kwargs):
        assert quotes==[proposal.evidence_quote] and proposal.text in answer
        if error:raise error
        return SupportReview(verdict,'The citation supplies the stated detail.',source.text,(source.text,))
    monkeypatch.setattr(module,'review_support',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.fact_readiness(client,proposal=proposal,evidence=evidence,
                                              source=source,base_eligible=base)
    return asyncio.run(call())


def test_supported_complete_quote_can_remain_ready(monkeypatch):
    assert run_fact(monkeypatch)['ready'] is True


@pytest.mark.parametrize('verdict',['unsupported','uncertain'])
def test_critic_approval_cannot_override_failed_citation_review(monkeypatch,verdict):
    result=run_fact(monkeypatch,verdict=verdict)
    assert result['ready'] is False and 'citation_support_'+verdict in result['reasons']


def test_necessary_rejection_is_never_overridden(monkeypatch):
    result=run_fact(monkeypatch,base=False)
    assert result['support_review'] is None and not result['ready']


@pytest.mark.parametrize('title',['Visual Inspiration','Set Atmosphere','Box Office Performance'])
def test_explicitly_discouraged_titles_withhold_without_semantic_review(monkeypatch,title):
    result=run_fact(monkeypatch,title=title)
    assert 'generic_title' in result['reasons'] and result['support_review'] is None


def test_names_from_broader_context_cannot_supply_missing_citation_identity(monkeypatch):
    result=run_fact(monkeypatch,text='Production designer Mira Cole built a practical chamber instead of green screens.')
    assert result['missing_mentions']==['Mira Cole'] and not result['ready']


@pytest.mark.parametrize('error',[ValueError('malformed secret'),httpx.HTTPError('private response')])
def test_missing_review_withholds_and_records_only_error_type(monkeypatch,error):
    result=run_fact(monkeypatch,error=error)
    assert not result['ready'] and result['error_type'] in ('ValueError','HTTPError')
    assert 'secret' not in str(result) and 'private response' not in str(result)


def test_quiz_new_clear_cannot_promote_critic_rejection(monkeypatch):
    from test_quiz_novelty import candidate
    proposals=ContentProposals(facts=[],questions=[candidate(),candidate('Where does Theo find the hidden key?')])
    async def review(*args,**kwargs):
        return [NoveltyReview('Q1','new',(),'clear','New fact.'),
                NoveltyReview('Q2','new',(),'clear','Another fact.')]
    monkeypatch.setattr(module,'review_quiz_novelty',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.quiz_readiness(client,proposals=proposals,
                quiz=SimpleNamespace(items=[]),base_eligible=['Q1'])
    assert asyncio.run(call())['ready_ids']==['Q1']


@pytest.mark.parametrize('novelty,clarity',[('duplicate','clear'),('uncertain','clear'),('new','needs_edit')])
def test_quiz_topic_or_wording_failure_withholds(monkeypatch,novelty,clarity):
    from test_quiz_novelty import candidate
    async def review(*args,**kwargs):return [NoveltyReview('Q1',novelty,(),'clear' if clarity=='clear' else clarity,'Needs checks.')]
    monkeypatch.setattr(module,'review_quiz_novelty',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.quiz_readiness(client,proposals=ContentProposals(facts=[],questions=[candidate()]),
                quiz=SimpleNamespace(items=[]),base_eligible=['Q1'])
    assert not asyncio.run(call())['ready_ids']


def test_quiz_malformed_review_preserves_withheld_report(monkeypatch):
    from test_quiz_novelty import candidate
    calls=[]
    async def review(*args,**kwargs):calls.append(1);raise ValueError('bad JSON')
    monkeypatch.setattr(module,'review_quiz_novelty',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.quiz_readiness(client,proposals=ContentProposals(facts=[],questions=[candidate()]),
                quiz=SimpleNamespace(items=[]),base_eligible=['Q1'])
    result=asyncio.run(call())
    assert not result['ready_ids'] and result['error_type']=='ValueError' and len(calls)==2


def test_quiz_transient_malformed_review_retries_once(monkeypatch):
    from test_quiz_novelty import candidate
    calls=[]
    async def review(*args,**kwargs):
        calls.append(1)
        if len(calls)==1:raise ValueError('bad first JSON')
        return [NoveltyReview('Q1','new',(),'clear','New fact.')]
    monkeypatch.setattr(module,'review_quiz_novelty',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.quiz_readiness(client,proposals=ContentProposals(facts=[],questions=[candidate()]),
                quiz=SimpleNamespace(items=[]),base_eligible=['Q1'])
    result=asyncio.run(call())
    assert result['ready_ids']==['Q1'] and len(calls)==2


@pytest.mark.parametrize('purpose_verdict,ready',[('supported',True),('unsupported',False),('uncertain',False)])
def test_explicit_purpose_needs_its_own_stated_reason(monkeypatch,purpose_verdict,ready):
    source,evidence,proposal=fixture(text='The production team built a practical chamber to support the story.')
    seen=[]
    async def review(*args,question,answer,quotes,**kwargs):
        seen.append(question)
        assert quotes==[proposal.evidence_quote]
        if question.startswith('Why'):
            assert answer=='to support the story'
            return SupportReview(purpose_verdict,'The purpose needs explicit support.',source.text,(source.text,))
        return SupportReview('supported','The general production detail is supported.',source.text,(source.text,))
    monkeypatch.setattr(module,'review_support',review)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.fact_readiness(client,proposal=proposal,evidence=evidence,source=source,base_eligible=True)
    result=asyncio.run(call())
    assert len(seen)==2 and result['ready'] is ready
    assert len(result['purpose_reviews'])==1


def test_purpose_routing_is_bounded_and_does_not_treat_preposition_as_intent():
    assert module.purpose_clauses('The team went to the chamber.')==[]
    assert len(module.purpose_clauses('The team built models to save money and to keep performers safe.'))==2
    with pytest.raises(ValueError):
        module.purpose_clauses('They acted to save money, to support the story and to reduce risk.')


@pytest.mark.parametrize('base_url,redirects',[('https://example.invalid',False),('http://127.0.0.1:11434',True)])
def test_fact_readiness_cannot_send_context_to_other_host_or_redirect(monkeypatch,base_url,redirects):
    source,evidence,proposal=fixture()
    async def call():
        async with httpx.AsyncClient(base_url=base_url,follow_redirects=redirects) as client:
            with pytest.raises(ValueError):
                await module.fact_readiness(client,proposal=proposal,evidence=evidence,source=source,base_eligible=True)
    asyncio.run(call())
