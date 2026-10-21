import asyncio,json
import httpx

from movie_companion.quiz_replacement_span_writer import answer_spans,generate_locked_drafts


def target():
    return {'title':'Film','question_id':'q1','old_question':'Where do they go?','replacement_brief':'Test how the flood forces the family to seek temporary shelter.',
        'remaining_questions':[],'evidence':{'citations':[{'source_label':'Source','source_ref':'https://en.wikipedia.org/x',
            'revision':'r1','excerpt':'After the flood destroys their home, the family must seek temporary shelter.'}]},
        'intent':{'question_id':'q1','focus':'the flood forcing the family from home','relation':'consequence',
            'required_concepts':[['flood'],['family'],['temporary shelter','shelter']],
            'forbidden_details':[],'expected_answer_shape':'outcome','difficulty':'general_viewer'}}


def test_answer_spans_are_exact_bounded_source_substrings():
    spans=answer_spans(target())
    source=target()['evidence']['citations'][0]['excerpt']
    assert spans and all(span['text'] in source for span in spans) and len(spans)<=30
    assert any('temporary shelter' in span['text'] for span in spans)


def test_answer_spans_remove_forbidden_duration_and_clause_fragments():
    value=target()
    value['replacement_brief']='Test the consequence of the run; omit the exact duration.'
    value['evidence']['citations'][0]['excerpt']=(
        'Heartbroken, Forrest spends the next three years in a relentless '
        'cross-country run, becoming famous again.')
    texts=[item['text'] for item in answer_spans(value)]
    assert 'a relentless cross-country run' in texts
    assert all('three years' not in text.casefold() for text in texts)
    assert all(not text.casefold().startswith(('but ','who ')) for text in texts)


def test_answer_spans_are_stable_and_bounded():
    assert answer_spans(target(),limit=8)==answer_spans(target(),limit=8)
    assert len(answer_spans(target(),limit=8))<=8


def test_answer_spans_abstain_when_every_exact_span_is_a_fragment():
    value=target()
    value['replacement_brief']='Test why the decision matters.'
    value['evidence']['citations'][0]['excerpt']='but who and therefore'
    assert answer_spans(value)==[]


def test_locked_writer_copies_selected_span_without_model_rewrite(monkeypatch):
    chosen=answer_spans(target())[0]
    async def fake(*args,**kwargs):
        return json.dumps({'items':[{'target_id':'T1','answer_span_id':chosen['span_id'],
            'question':'What consequence does the flood have for the family?',
            'distractors':['They inherit a mansion','They leave the city','They repair the house']} ]})
    monkeypatch.setattr('movie_companion.quiz_replacement_span_writer.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await generate_locked_drafts(client,[target()])
    drafts,info=asyncio.run(run());draft=drafts.items[0]
    assert draft.options[0]==chosen['text']
    assert draft.options[0] in draft.evidence_quote
    assert info['T1']['writer_problems']==[]


def test_locked_writer_abstains_on_duplicate_distractors(monkeypatch):
    chosen=answer_spans(target())[0]
    async def fake(*args,**kwargs):
        return json.dumps({'items':[{'target_id':'T1','answer_span_id':chosen['span_id'],
            'question':'What consequence does the flood have for the family?',
            'distractors':['They leave the city','They leave the city','They repair the house']} ]})
    monkeypatch.setattr('movie_companion.quiz_replacement_span_writer.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await generate_locked_drafts(client,[target()])
    drafts,info=asyncio.run(run())
    assert drafts.items==[]
    assert info['T1']['writer_problems']==['invalid_distractors']


def test_locked_writer_withholds_a_candidate_that_misses_reviewed_intent(monkeypatch):
    chosen=next(item for item in answer_spans(target()) if item['text']=='seek temporary shelter')
    async def fake(*args,**kwargs):
        return json.dumps({'items':[{'target_id':'T1','answer_span_id':chosen['span_id'],
            'question':'What happens after the storm?',
            'distractors':['They inherit a mansion','They leave the city','They repair the house']} ]})
    monkeypatch.setattr('movie_companion.quiz_replacement_span_writer.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await generate_locked_drafts(client,[target()])
    drafts,info=asyncio.run(run())
    assert drafts.items==[]
    assert info['T1']['writer_problems']==['missing_required_concept']


def test_locked_writer_isolates_intent_failure_from_valid_sibling(monkeypatch):
    first=target();second={**target(),'question_id':'q2',
        'intent':{**target()['intent'],'question_id':'q2'}}
    first_span=answer_spans(first)[0];second_span=answer_spans(second)[0]
    async def fake(*args,**kwargs):
        return json.dumps({'items':[
            {'target_id':'T1','answer_span_id':first_span['span_id'],
             'question':'What consequence does the flood have for the family?',
             'distractors':['They inherit a mansion','They leave the city','They repair the house']},
            {'target_id':'T2','answer_span_id':second_span['span_id'],
             'question':'Where do they go?',
             'distractors':['They inherit a mansion','They leave the city','They repair the house']}]})
    monkeypatch.setattr('movie_companion.quiz_replacement_span_writer.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await generate_locked_drafts(client,[first,second])
    drafts,info=asyncio.run(run())
    assert [item.target_id for item in drafts.items]==['T1']
    assert info['T1']['writer_problems']==[]
    assert 'answer_shape_mismatch' in info['T2']['writer_problems']
