import asyncio
import json

import httpx
import pytest

from movie_companion.content_proposals import ContentProposals, ProposalEvidence
from movie_companion.structured_content_review import Assessment, decision_for, review_proposals


def assessment(**changes):
    return Assessment.model_validate({'item_id':'Q1','support':'supported','content':'eligible',
        'supported_option_indices':[1],'plausible_options':True,
        'narrative_focus':'cause_or_consequence','narrative_significance':'central',
        'reason':'The selected option is supported by the quotation.',**changes})


@pytest.mark.parametrize('changes,expected',[
    ({},'accept'),({'support':'contradicted_or_exceeds'},'reject'),
    ({'support':'insufficient_context'},'uncertain'),({'content':'subjective'},'reject'),
    ({'content':'granular_detail','narrative_focus':'granular_recall','narrative_significance':'granular'},'reject'),
    ({'narrative_focus':'granular_recall'},'reject'),
    ({'narrative_significance':'granular'},'reject'),
    ({'narrative_focus':'not_applicable','narrative_significance':'not_applicable'},'reject'),
    ({'supported_option_indices':[0,1]},'reject'),({'supported_option_indices':[0]},'reject'),
    ({'supported_option_indices':[]},'reject'),({'plausible_options':False},'reject'),
])
def test_code_requires_all_criteria_and_exact_supported_answer(changes,expected):
    assert decision_for(assessment(**changes),kind='question',correct_index=1)==expected


def test_fact_metadata_and_missing_context_have_distinct_decisions():
    base={'item_id':'F1','supported_option_indices':[],'plausible_options':None,
          'narrative_focus':'not_applicable','narrative_significance':'not_applicable'}
    assert decision_for(assessment(**base),kind='fact')=='accept'
    assert decision_for(assessment(**base,content='basic_metadata'),kind='fact')=='reject'
    assert decision_for(assessment(**base,support='insufficient_context'),kind='fact')=='uncertain'
    with pytest.raises(ValueError): decision_for(assessment(),kind='fact')
    with pytest.raises(ValueError): decision_for(assessment(plausible_options=None),kind='question',correct_index=1)
    with pytest.raises(ValueError): decision_for(assessment(content='plot_in_facts'),kind='question',correct_index=1)
    with pytest.raises(ValueError): decision_for(assessment(**base,content='production_trivia'),kind='fact')


@pytest.mark.parametrize('indices',[[1,1],[4],[-1],['1'],[True]])
def test_invalid_or_duplicate_option_indices_fail_schema_validation(indices):
    with pytest.raises(ValueError): assessment(supported_option_indices=indices)


def payload():
    text='The detective gave the photograph to the station clerk and the ticket to the porter.'
    evidence=[ProposalEvidence(passage_id='P1',purpose='story',text=text)]
    proposals=ContentProposals.model_validate({'facts':[],'questions':[{'question':'Who received the photograph?',
        'options':['The porter','The station clerk','The conductor','The platform guard'],
        'correct_index':0,'passage_id':'P1','evidence_quote':text}]})
    return proposals,evidence


def test_selected_answer_is_explicit_and_model_cannot_override_computed_decision():
    proposals,evidence=payload()
    async def run():
        def handler(request):
            body=json.loads(request.content)
            candidates=json.loads(body['messages'][0]['content'].split('CANDIDATES JSON:\n')[1])
            assert candidates[0]['selected_answer']=={'index':0,'text':'The porter'}
            assert candidates[0]['indexed_options'][1]=={'index':1,'text':'The station clerk'}
            assert 'tools' not in body and body['think'] is False
            # Even a falsely "supported" selected answer cannot override a
            # separate assessment identifying index 1 as the only valid answer.
            response={'items':[assessment().model_dump()]}
            return httpx.Response(200,json={'message':{'content':json.dumps(response)}})
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            result=await review_proposals(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
            assert result.items[0].decision=='reject'
            assert result.items[0].assessment.supported_option_indices==[1]
    asyncio.run(run())


@pytest.mark.parametrize('change',['missing','duplicate','invented','extra-decision','bad-fact-options','missing-narrative'])
def test_incomplete_or_illegal_assessments_fail_closed(change):
    proposals,evidence=payload()
    response={'items':[assessment().model_dump()]}
    if change=='missing': response['items']=[]
    elif change=='duplicate': response['items']*=2
    elif change=='invented': response['items'][0]['item_id']='Q2'
    elif change=='extra-decision': response['items'][0]['decision']='accept'
    elif change=='bad-fact-options': response['items'][0]['plausible_options']=None
    else: del response['items'][0]['narrative_focus']
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(
            lambda r:httpx.Response(200,json={'message':{'content':json.dumps(response)}}))) as client:
            with pytest.raises(ValueError):
                await review_proposals(client,model='local',proposals=proposals,evidence=evidence)
    asyncio.run(run())


def test_bad_evidence_is_rejected_before_any_model_call():
    proposals,evidence=payload()
    proposals.questions[0].passage_id='P9'
    async def run():
        def forbidden(request): pytest.fail('Invalid evidence must not reach inference')
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(forbidden)) as client:
            result=await review_proposals(client,model='local',proposals=proposals,evidence=evidence)
            assert result.items[0].decision=='reject' and result.items[0].assessment is None
            assert result.model_calls==0
    asyncio.run(run())


def test_fact_and_quiz_branches_are_separate_and_bounded_to_two_calls():
    proposals,evidence=payload()
    background='The crew sculpted miniature storm clouds from cotton for the skyline scene.'
    evidence.append(ProposalEvidence(passage_id='P2',purpose='background',text=background))
    proposals.facts=ContentProposals.model_validate({'questions':[], 'facts':[{
        'title':'Cotton storm clouds','text':background,'passage_id':'P2','evidence_quote':background}]}).facts
    seen=[]
    async def run():
        def handler(request):
            body=json.loads(request.content)
            branch=json.loads(body['messages'][0]['content'].split('CANDIDATES JSON:\n')[1])
            kinds={c['kind'] for c in branch}
            assert len(kinds)==1
            kind=next(iter(kinds)); seen.append(kind)
            properties=body['format']['$defs']['Assessment']['properties']
            required=body['format']['$defs']['Assessment']['required']
            assert 'narrative_focus' in required and 'narrative_significance' in required
            if kind=='fact':
                assert 'production_trivia' not in properties['content']['enum']
                assert properties['supported_option_indices']['maxItems']==0
                assert properties['plausible_options']=={'type':'null'}
                assert properties['narrative_focus']['enum']==['not_applicable']
            else:
                assert 'plot_in_facts' not in properties['content']['enum']
                assert 'granular_detail' in properties['content']['enum']
                assert properties['plausible_options']=={'type':'boolean'}
                assert 'granular_recall' in properties['narrative_focus']['enum']
                assert 'not_applicable' not in properties['narrative_focus']['enum']
            item=assessment(item_id='F1',supported_option_indices=[],plausible_options=None,
                narrative_focus='not_applicable',narrative_significance='not_applicable') if kind=='fact' else assessment()
            return httpx.Response(200,json={'message':{'content':json.dumps({'items':[item.model_dump()]})}})
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            result=await review_proposals(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
            assert result.model_calls==2 and len(result.items)==2
            assert result.items[0].decision=='accept' and result.items[1].decision=='reject'
    asyncio.run(run())
    assert seen==['fact','question']


@pytest.mark.parametrize('url,redirects',[('https://evil.example',False),('http://127.0.0.1:11434',True)])
def test_remote_or_redirecting_clients_cannot_be_used(url,redirects):
    proposals,evidence=payload()
    async def run():
        async with httpx.AsyncClient(base_url=url,follow_redirects=redirects) as client:
            with pytest.raises(ValueError):
                await review_proposals(client,model='local',proposals=proposals,evidence=evidence)
    asyncio.run(run())
