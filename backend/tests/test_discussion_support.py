import asyncio
import json
import httpx
import pytest

from movie_companion.discussion_support import review_support


@pytest.mark.parametrize('verdict', ['supported','unsupported','uncertain'])
def test_strict_review_contract_and_bounded_local_request(verdict):
    def handler(request):
        body=json.loads(request.content)
        assert body['options']['num_predict']==768
        assert body['format']['additionalProperties'] is False
        assert 'selected_evidence' in body['messages'][0]['content']
        return httpx.Response(200,json={'message':{'content':json.dumps({'verdict':verdict,'reason':'Fixture reason','evidence_answer':'A reason.','evidence_quotes':['The source states a useful reason.']})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as client:
            result=await review_support(client,model='fixture',question='Why?',answer='A reason.',quotes=['The source states a useful reason.'])
            assert result.verdict==verdict
    asyncio.run(run())


@pytest.mark.parametrize('raw', ['not JSON','[]','{}','{"verdict":"yes","reason":"A reason"}',
                               '{"verdict":"supported","reason":123}',
                               '{"verdict":"supported","reason":" "}',
                               '{"verdict":"supported","reason":"A reason","tool":"delete"}'])
def test_malformed_reviews_fail_closed(raw):
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'message':{'content':raw}}))) as client:
            with pytest.raises(ValueError):await review_support(client,model='fixture',question='Why?',answer='A reason.',quotes=['The source states a useful reason.'])
    asyncio.run(run())


@pytest.mark.parametrize('mutation', ['quote','duplicate','empty-support','no-answer','extra-key','reason-type'])
def test_structured_review_rejects_invalid_proof_even_when_verdict_says_supported(mutation):
    quote='The source states a useful reason.'
    data={'verdict':'supported','reason':'A reason','evidence_answer':'A reason.', 'evidence_quotes':[quote]}
    if mutation=='quote':data['evidence_quotes']=['Invented quote outside the offered evidence.']
    if mutation=='duplicate':data['evidence_quotes']=[quote,quote]
    if mutation=='empty-support':data['evidence_quotes']=[]
    if mutation=='no-answer':data['evidence_answer']='Insufficient evidence.'
    if mutation=='extra-key':data['tool']='publish'
    if mutation=='reason-type':data['reason']=False
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(
            lambda _:httpx.Response(200,json={'message':{'content':json.dumps(data)}}))) as client:
            with pytest.raises(ValueError):await review_support(client,model='fixture',question='Why?',answer='A reason.',quotes=[quote])
    asyncio.run(run())
