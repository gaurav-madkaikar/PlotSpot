import asyncio
import json
from pathlib import Path

import httpx
import pytest

from movie_companion import background_fact_review as review
from movie_companion.structured_content_review import Assessment,StructuredDecision,StructuredReview
from movie_companion.content_proposals import ContentProposals,ProposalEvidence,EvidenceOrigin


def inputs():
    text='The crew built a practical lighting rig for the production.'
    return ContentProposals(facts=[dict(title='A practical lighting rig',
        text='The filmmakers built a practical lighting rig for their production.',
        passage_id='P1',evidence_quote=text)],questions=[]),[ProposalEvidence(passage_id='P1',purpose='background',text=text)]


def structured(item_id='F1',decision='accept',content='eligible',reason='The supplied production quote supports the complete claim.'):
    assessment=Assessment(item_id=item_id,support='supported',content=content,
        supported_option_indices=[],plausible_options=None,narrative_focus='not_applicable',
        narrative_significance='not_applicable',reason=reason)
    return StructuredDecision(item_id=item_id,decision=decision,reason=reason,assessment=assessment)


@pytest.mark.parametrize('decision',['accept','reject','uncertain'])
@pytest.mark.parametrize('missing',[[],['Bong Joon-ho']])
def test_code_withholds_missing_context_without_claiming_falsehood(decision,missing):
    assessment=review.FactAssessment(item_id='F1',missing_mentions=missing,semantic_decision=decision,
                                    content='eligible',
                                    reason='The semantic reviewer checked the actual supplied quote.')
    assert review.decision_for(assessment)==('uncertain' if missing else decision)


@pytest.mark.parametrize('claim,context,missing',[
    ('Director Bong Joon-ho chose to avoid traditional shot coverage.','Bong chose to avoid traditional shot coverage.',['Bong Joon-ho']),
    ('Rian Johnson named characters after musicians.','Johnson named characters after musicians.',['Rian Johnson']),
    ('Milena Canonero researched period artworks.','Canonero researched period artworks.',['Milena Canonero']),
    ('Greig Fraser used sandscreens for desert lighting.','Sandscreens simulated desert lighting.',['Greig Fraser']),
    ('Donald H. Hewitt wrote English dialogue.','Donald H. Hewitt wrote the English dialogue.',[]),
    ('The crew studied Joni Mitchell and Man Ray.','Joni Mitchell and Man Ray inspired the production.',[]),
    ('Denis Villeneuve studied James Turrell’s artwork.','Denis Villeneuve and James Turrell inspired the production.',[]),
    ('Roger Deakins used a practical chamber.','Young filmed the practical chamber.',['Roger Deakins']),
    ('Steely Dan’s Donald Fagen inspired the naming practice.',"Steely Dan's Donald Fagen inspired the names.",[]),
    ('The film used a practical chamber.','The chamber was built for filming.',[]),
])
def test_conservative_multiword_name_coverage(claim,context,missing):
    p=ProposalEvidence(passage_id='P1',purpose='background',text=context)
    assert review.missing_mentions(claim,p)==missing


@pytest.mark.parametrize('movie_id,title',[(546554,'Knives Out'),(37165,'The Truman Show'),(120467,'The Grand Budapest Hotel')])
def test_registered_movie_title_is_not_mistaken_for_a_missing_person(movie_id,title):
    text='The crew used practical lighting for desert backgrounds.'
    p=ProposalEvidence(passage_id='P1',purpose='background',text=text,
        origin=EvidenceOrigin(movie_id=movie_id,source_id='fixture',source_ref='https://example.org',revision='v1',section_title='Production',section_category='production',start=0,end=len(text)))
    assert review.missing_mentions(title+' used practical lighting.',p)==[]


def test_editorial_title_casing_does_not_become_a_missing_name(monkeypatch):
    proposals,evidence=inputs()
    proposals.facts[0].title='Practical Lighting Rig'
    async def critic(*a,**kw):
        return StructuredReview(items=[structured(reason='The source supports the factual body and editorial title.')])
    monkeypatch.setattr(review,'semantic_review',critic)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            result=await review.review_proposals(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
            assert result.items[0].decision=='accept'
            assert result.items[0].assessment.missing_mentions==[]
    asyncio.run(run())


def test_semantic_acceptance_cannot_override_missing_name(monkeypatch):
    proposals,evidence=inputs()
    proposals.facts[0].text='Roger Deakins built a practical lighting rig for the film.'
    async def critic(*a,**kw):return StructuredReview(items=[structured(reason='Mock acceptance of a claim without identity evidence.')])
    monkeypatch.setattr(review,'semantic_review',critic)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            result=await review.review_proposals(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
            assert result.items[0].decision=='uncertain'
            assert result.items[0].assessment.missing_mentions==['Roger Deakins']
    asyncio.run(run())


@pytest.mark.parametrize('ids',[[],['F1','F1'],['F2']])
def test_incomplete_duplicate_unknown_semantic_reviews_fail_closed(monkeypatch,ids):
    async def critic(*a,**kw):return StructuredReview(items=[structured(item_id=i,reason='A controlled incomplete response fixture.') for i in ids])
    monkeypatch.setattr(review,'semantic_review',critic)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            with pytest.raises(ValueError):await review.review_proposals(client,model='qwen3.5:9b',proposals=inputs()[0],evidence=inputs()[1])
    asyncio.run(run())


def test_quote_gate_has_priority_over_a_missing_name(monkeypatch):
    proposals,evidence=inputs()
    proposals.facts[0].text='Roger Deakins built a lighting rig for the film.'
    proposals.facts[0].evidence_quote='This invented quote is absent from the source.'
    async def critic(*a,**kw):return StructuredReview(items=[structured(reason='Mock approval must not override deterministic checks.')])
    monkeypatch.setattr(review,'semantic_review',critic)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            result=await review.review_proposals(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
            assert result.items[0].decision=='reject'
    asyncio.run(run())


@pytest.mark.parametrize('host,redirects',[('https://evil.example',False),('http://127.0.0.1:11434',True)])
def test_bad_clients_never_reach_model(monkeypatch,host,redirects):
    async def forbidden(*a,**kw):pytest.fail('No model calls allowed')
    monkeypatch.setattr(review,'semantic_review',forbidden)
    async def run():
        async with httpx.AsyncClient(base_url=host,follow_redirects=redirects) as client:
            with pytest.raises(ValueError):await review.review_proposals(client,model='qwen3.5:9b',proposals=inputs()[0],evidence=inputs()[1])
    asyncio.run(run())


def test_new_reviewer_invalidates_only_background_fingerprint(monkeypatch):
    from movie_companion.background_fact_workflow import fingerprint
    from movie_companion.story_rag import policy_fingerprint
    before=fingerprint();story=policy_fingerprint();original=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p:original(p)+(b'changed' if p.name=='background_fact_review.py' else b''))
    assert fingerprint()!=before and policy_fingerprint()==story
