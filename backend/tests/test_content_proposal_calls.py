import asyncio
import json

import httpx
import pytest

from movie_companion.content_proposals import ContentProposals, ProposalEvidence
from movie_companion.content_proposal_learning import propose_content
from movie_companion.content_proposal_review import review_proposals

TEXT = 'The crew used a rotating corridor to film the changing gravity sequence.'


def evidence():
    return [ProposalEvidence(passage_id='P1',purpose='background',text=TEXT)]


def proposals():
    return ContentProposals.model_validate({'facts':[{'title':'A rotating corridor','text':TEXT,
        'passage_id':'P1','evidence_quote':TEXT}],'questions':[]})


def test_proposal_http_contract_and_structured_reply():
    calls = []
    async def run():
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'message':{'content':proposals().model_dump_json()}})
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            result = await propose_content(client,model='llama3.2:3b',movie_title='Example film',evidence=evidence())
            assert result == proposals()
    asyncio.run(run())
    assert len(calls) == 1 and calls[0].url.path == '/api/chat'
    body = json.loads(calls[0].content)
    assert body['stream'] is False and body['model'] == 'llama3.2:3b'
    assert body['format']['$defs']['FactProposal']['properties']['passage_id']['enum'] == ['P1']
    assert 'untrusted data' in body['messages'][0]['content']
    assert TEXT in body['messages'][0]['content']
    assert 'tools' not in body


@pytest.mark.parametrize('failure',['remote','redirect','blank-title','too-long-title','malformed','extra-action','http'])
def test_proposal_failures_propagate_without_other_actions(failure):
    async def run():
        def handler(request):
            if failure == 'http': return httpx.Response(503)
            raw = 'not json' if failure == 'malformed' else json.dumps({'facts':[],'questions':[],'tool_call':'delete'})
            return httpx.Response(200,json={'message':{'content':raw}})
        async with httpx.AsyncClient(base_url='https://evil.example' if failure=='remote' else 'http://127.0.0.1:11434',
                                    follow_redirects=failure=='redirect',transport=httpx.MockTransport(handler)) as client:
            title = '' if failure=='blank-title' else 'x'*201 if failure=='too-long-title' else 'Example'
            with pytest.raises((ValueError,httpx.HTTPError)):
                await propose_content(client,model='local',movie_title=title,evidence=evidence())
    asyncio.run(run())


def test_deterministic_rejection_bypasses_critic_and_cannot_be_overridden():
    data = proposals().model_dump(); data['facts'][0]['passage_id'] = 'P9'
    async def run():
        def forbidden(request): pytest.fail('Invalid evidence must not call the critic')
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(forbidden)) as client:
            result = await review_proposals(client,model='local',proposals=ContentProposals.model_validate(data),evidence=evidence())
            assert result.items[0].decision == 'reject'
    asyncio.run(run())


@pytest.mark.parametrize('response',[
    {'items':[]},
    {'items':[{'item_id':'F2','decision':'accept','reason':'A supported concise fact.'}]},
    {'items':[{'item_id':'F1','decision':'accept','reason':'A supported concise fact.'}]*2},
    {'items':[{'item_id':'F1','decision':'accept','reason':'A supported concise fact.'}], 'publish':True},
])
def test_incomplete_or_invented_critic_decisions_fail_closed(response):
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={'message':{'content':json.dumps(response)}}))) as client:
            with pytest.raises(ValueError):
                await review_proposals(client,model='local',proposals=proposals(),evidence=evidence())
    asyncio.run(run())


def test_valid_critic_observation_is_returned_without_publication():
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={'message':{'content':json.dumps({'items':[
                {'item_id':'F1','decision':'accept','reason':'The quote directly supports this concise fact.'}]})}}))) as client:
            result = await review_proposals(client,model='local',proposals=proposals(),evidence=evidence())
            assert result.items[0].decision == 'accept'
    asyncio.run(run())


def test_qwen_critic_has_bounded_non_thinking_payload():
    async def run():
        def handler(request):
            body = json.loads(request.content)
            assert body['think'] is False
            assert body['options']['num_predict'] == 1800
            return httpx.Response(200,json={'message':{'content':json.dumps({'items':[
                {'item_id':'F1','decision':'uncertain','reason':'More semantic context is needed.'}]})}})
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            result = await review_proposals(client,model='qwen3.5:9b',proposals=proposals(),evidence=evidence())
            assert result.items[0].decision == 'uncertain'
    asyncio.run(run())


STORY = 'Cobb accepts the job because Saito promises to clear his criminal status so he can return to his children.'


def story_evidence():
    return ProposalEvidence(passage_id='P2', purpose='story', text=STORY)


def story_proposal():
    return {'question':'What does Saito promise Cobb in return for accepting the job?',
            'options':['Clear his criminal status','Give him a new identity','Buy his company','Teach him dream-sharing'],
            'correct_index':0, 'passage_id':'P2', 'evidence_quote':STORY}


def test_mixed_evidence_uses_two_isolated_sequential_calls():
    bodies = []
    active = 0
    async def handler(request):
        nonlocal active
        active += 1
        assert active == 1
        body = json.loads(request.content)
        bodies.append(body)
        await asyncio.sleep(0)
        if len(bodies) == 1:
            reply = proposals().model_dump()
        else:
            reply = {'facts':[], 'questions':[story_proposal()]}
        active -= 1
        return httpx.Response(200, json={'message':{'content':json.dumps(reply)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',
                                    transport=httpx.MockTransport(handler)) as client:
            return await propose_content(client, model='qwen3.5:9b', movie_title='Inception',
                                         evidence=evidence()+[story_evidence()])
    result = asyncio.run(run())
    assert len(bodies) == 2
    assert len(result.facts) == 1 and len(result.questions) == 1
    for body, included, excluded, key, other, record, alias in [
        (bodies[0],TEXT,STORY,'facts','questions','FactProposal','P1'),
        (bodies[1],STORY,TEXT,'questions','facts','QuizProposal','P2')]:
        prompt = body['messages'][0]['content']
        assert included in prompt and excluded not in prompt
        assert body['format']['properties'][other]['maxItems'] == 0
        assert body['format']['properties'][key]['maxItems'] == 2
        assert body['format']['$defs'][record]['properties']['passage_id']['enum'] == [alias]
        assert body['think'] is False and body['options']['num_predict'] == 1536
        assert 'tools' not in body


def test_story_only_skips_fact_call_and_empty_output_is_valid_abstention():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':'{"facts":[],"questions":[]}'}})
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            return await propose_content(client,model='local',movie_title='Example',evidence=[story_evidence()])
    result = asyncio.run(run())
    assert not result.facts and not result.questions
    assert len(calls) == 1
    assert calls[0]['format']['properties']['facts']['maxItems'] == 0


@pytest.mark.parametrize('violation', ['wrong-array','wrong-alias','too-many','second-branch-alias'])
def test_branch_restrictions_are_enforced_in_python_even_if_model_ignores_schema(violation):
    calls = []
    def handler(request):
        calls.append(request)
        reply = proposals().model_dump()
        if violation == 'wrong-array':
            reply['questions'] = [story_proposal()]
        elif violation == 'wrong-alias':
            reply['facts'][0]['passage_id'] = 'P2'
        elif violation == 'too-many':
            reply['facts'] *= 3
        elif len(calls) == 2:
            item = story_proposal(); item['passage_id'] = 'P1'
            reply = {'facts':[], 'questions':[item]}
        return httpx.Response(200,json={'message':{'content':json.dumps(reply)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError,match='branch contract'):
                await propose_content(client,model='local',movie_title='Example',
                                      evidence=evidence()+[story_evidence()])
    asyncio.run(run())
    assert len(calls) == (2 if violation == 'second-branch-alias' else 1)


def test_second_branch_failure_propagates_without_retry_or_returning_partial_batch():
    calls = []
    def handler(request):
        calls.append(request)
        return (httpx.Response(200,json={'message':{'content':proposals().model_dump_json()}})
                if len(calls)==1 else httpx.Response(503))
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(httpx.HTTPError):
                await propose_content(client,model='local',movie_title='Example',
                                      evidence=evidence()+[story_evidence()])
    asyncio.run(run())
    assert len(calls) == 2
