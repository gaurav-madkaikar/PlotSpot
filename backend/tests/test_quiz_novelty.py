import asyncio
import json

import httpx
import pytest

from movie_companion import quiz_novelty as module
from movie_companion.content_proposals import QuizProposal


def candidate(question='Where does Mira find the key?',answer='Inside the clock'):
    return QuizProposal(question=question,options=[answer,'Below the table','Inside the piano','Beside the fireplace'],
        correct_index=0,passage_id='P1',evidence_quote='Mira finds the key inside the clock in the hallway.')


def decision(candidate_id='Q1',novelty='new',matches=None,clarity='clear'):
    return {'candidate_id':candidate_id,'novelty':novelty,'matches':matches or [],
            'clarity':clarity,'reason':'The question tests a different specific story fact.'}


def run(monkeypatch,items,*,candidates=None,existing=None,raw=None,adjudication_context=None):
    async def verify(*args):pass
    async def chat(*args,**kwargs):
        assert kwargs['max_output_tokens'] in (900,600) and kwargs['think'] is False
        if kwargs['max_output_tokens']==900:
            assert 'CORRECT ANSWER' in kwargs['prompt'] and 'untrusted DATA' in kwargs['prompt']
            if adjudication_context is not None:
                assert adjudication_context[0]['candidate_intent'] in kwargs['prompt']
            return raw if raw is not None else json.dumps({'items':[
                {k:v for k,v in item.items() if k!='clarity'} for item in items]})
        return json.dumps({'items':[{'candidate_id':item['candidate_id'],'clarity':item['clarity'],
                                     'reason':'The stem wording is natural.'}
                                    for item in items if item['novelty']=='new']})
    monkeypatch.setattr(module,'verify_local_model',verify)
    monkeypatch.setattr(module,'chat_once',chat)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.review_quiz_novelty(client,candidates=candidates or [candidate()],
                existing=[] if existing is None else existing,
                adjudication_context=adjudication_context)
    return asyncio.run(call())


def test_paraphrased_topic_retains_matching_bank_id(monkeypatch):
    result=run(monkeypatch,[decision(novelty='duplicate',matches=['B1'])],
               existing=[{'question':'In what object is the key hidden?','answer':'The clock'}])
    assert result[0].novelty=='duplicate' and result[0].matches==('B1',)


def test_same_correct_answer_is_not_automatically_duplicate(monkeypatch):
    result=run(monkeypatch,[decision()],existing=[{'question':'Where does Theo hide the letter?','answer':'Inside the clock'}])
    assert result[0].novelty=='new'


def test_adjudication_context_is_bounded_untrusted_comparison_data(monkeypatch):
    context=[{'candidate_intent':'a relationship changes when the character becomes a father',
        'compared_bank_intent':'recall the child name',
        'decision_rule':'same viewer knowledge means duplicate'}]
    result=run(monkeypatch,[decision()],adjudication_context=context)
    assert result[0].novelty=='new'


def test_expanded_name_for_same_subject_is_a_duplicate_without_model(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('answer alias needs no inference')
    monkeypatch.setattr(module,'chat_once',forbidden)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.review_quiz_novelty(
                client,
                candidates=[candidate('What is the name of the warden at Shawshank?','Samuel Norton')],
                existing=[{'question':'What is the name of the religious warden at Shawshank?',
                           'answer':'Norton'}])
    result=asyncio.run(call())
    assert result[0].novelty=='duplicate' and result[0].matches==('B1',)


def test_exact_stem_blocks_even_if_correct_answer_changed_without_model(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('exact duplicates need no inference')
    monkeypatch.setattr(module,'chat_once',forbidden)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.review_quiz_novelty(client,candidates=[candidate()],
                existing=[{'question':candidate().question.upper(),'answer':'A different answer'}])
    assert asyncio.run(call())[0].novelty=='duplicate'


@pytest.mark.parametrize('item',[
    decision(novelty='duplicate'),decision(novelty='new',matches=['B1']),
    decision(matches=['B99']),decision(novelty='duplicate',matches=['Q1']),
    decision(novelty='duplicate',matches=['Q2']),decision(novelty='duplicate',matches=['B1','B1']),
    decision(candidate_id='Q9'),decision(novelty='perfect'),
    {**decision(),'unexpected':'field'}, {**decision(),'reason':True},
])
def test_invalid_provenance_or_schema_is_rejected(monkeypatch,item):
    with pytest.raises(ValueError):run(monkeypatch,[item],existing=[{'question':'Where is the letter?','answer':'Below the table'}])


@pytest.mark.parametrize('items',[[],[decision(),decision()]])
def test_missing_or_duplicate_candidate_review_is_rejected(monkeypatch,items):
    with pytest.raises(ValueError):run(monkeypatch,items)


def test_earlier_candidate_is_valid_match_and_output_order_is_canonical(monkeypatch):
    result=run(monkeypatch,[decision('Q2','duplicate',['Q1'])],
        candidates=[candidate('Where is the hidden key located?'),candidate('In what object does Mira discover the key?')])
    assert [r.candidate_id for r in result]==['Q1','Q2']
    assert result[1].matches==('Q1',)


def test_context_budgets_fail_before_inference(monkeypatch):
    with pytest.raises(ValueError):run(monkeypatch,[],existing=[{'question':'x'*251,'answer':'A'}])
    with pytest.raises(ValueError):run(monkeypatch,[],candidates=[candidate()]*4)
    with pytest.raises(ValueError):run(monkeypatch,[],existing=[{'question':'   ','answer':'A'}])


def test_cancellation_propagates(monkeypatch):
    async def cancelled(*args,**kwargs):raise asyncio.CancelledError
    async def verify(*args):pass
    monkeypatch.setattr(module,'verify_local_model',verify)
    monkeypatch.setattr(module,'chat_once',cancelled)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            with pytest.raises(asyncio.CancelledError):
                await module.review_quiz_novelty(client,candidates=[candidate()],existing=[])
    asyncio.run(call())


def test_incomplete_how_complement_withholds_without_model(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('narrow stem check requires no inference')
    monkeypatch.setattr(module,'chat_once',forbidden)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await module.review_quiz_novelty(client,candidates=[candidate('How are the ships revealed to be?','Wooden models')],existing=[])
    result=asyncio.run(call())
    assert result[0].clarity=='needs_edit' and result[0].novelty=='uncertain'


def test_invalid_wording_result_withholds(monkeypatch):
    with pytest.raises(ValueError):run(monkeypatch,[decision(clarity='perfect')])
