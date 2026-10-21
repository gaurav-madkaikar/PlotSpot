import asyncio
import json

import httpx
import pytest

import movie_companion.grounding_learning as grounding
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit


HIT = RetrievalHit(EmbeddedPassage(
    "sound", 101, "The fictional sound team recorded a washing machine.",
    [1.0, 0.0], "test-model", "Authored fixture", "safe",
), 0.8)


def test_prompt_contains_question_and_serialized_evidence():
    evidence = json.dumps([{"passage_id": "sound", "text": HIT.passage.text}])
    prompt = grounding.build_grounded_prompt("How was the sound made?", evidence)
    assert "How was the sound made?" in prompt
    assert evidence in prompt


def test_prompt_requests_explicit_json_contract():
    prompt = grounding.build_grounded_prompt("Question", "[]")
    for field in ("status", "answer", "evidence_quotes", "answered", "insufficient_evidence"):
        assert field in prompt


def run_reply(monkeypatch, payload, *, hits=None, question="How was the sound made?", status_code=200):
    captured = []
    def builder(question, evidence_json):
        captured.append(json.loads(evidence_json))
        return "Test prompt"
    monkeypatch.setattr(grounding, "build_grounded_prompt", builder)
    def handler(request):
        assert request.url.path == "/api/chat"
        assert json.loads(request.content)["model"] == "llama3.2:3b"
        body = json.loads(request.content)
        assert body["format"]["properties"]["evidence_quotes"]["maxItems"] == 3
        assert body["format"]["additionalProperties"] is False
        assert body["options"] == {"temperature": 0, "seed": 7}
        return httpx.Response(status_code, json={"message": {"content": payload}})
    async def run():
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)) as client:
            return await grounding.answer_from_hits(
                client, model="llama3.2:3b", question=question,
                hits=[HIT] if hits is None else hits,
            )
    return asyncio.run(run()), captured


def test_accepts_supplied_ids_and_sends_text_without_vectors(monkeypatch):
    reply = json.dumps({"status": "answered", "answer": "Recorded a washing machine.", "evidence_quotes": [HIT.passage.text]})
    answer, captured = run_reply(monkeypatch, reply)
    assert answer.citation_ids == ("sound",)
    assert captured == [[{"text": HIT.passage.text, "source_label": "Authored fixture",
                         "support_options": [HIT.passage.text]}]]


def test_quote_options_preserve_source_and_clipped_context():
    from dataclasses import replace
    text = "A complete sentence contains a useful fact. trailing fragment with an important detail"
    hit = RetrievalHit(replace(HIT.passage, text=text), .8)
    options = grounding._quote_options([hit, hit])
    assert options == ["A complete sentence contains a useful fact.", text]
    assert all(option in text for option in options)


def test_schema_offers_only_verbatim_choices_and_membership_is_enforced(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body['format']['properties']['evidence_quotes']['items']['enum'] == [HIT.passage.text]
        assert 'support_options' in body['messages'][0]['content']
        # This real substring was not offered as an independent support option.
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'status': 'answered', 'answer': 'A washing machine.',
            'evidence_quotes': ['sound team recorded a washing machine.']})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError, match='not an offered'):
                await grounding.answer_from_hits(client, model='fixture', question='How?', hits=[HIT])
    asyncio.run(run())


def test_no_bounded_excerpt_abstains_without_model(monkeypatch):
    from dataclasses import replace
    hit = RetrievalHit(replace(HIT.passage, text='x' * 700), .8)
    answer, captured = run_reply(monkeypatch, 'must not be used', hits=[hit])
    assert answer.status == 'insufficient_evidence'
    assert captured == []


def test_empty_evidence_abstains_without_chat(monkeypatch):
    answer, captured = run_reply(monkeypatch, "must not be used", hits=[])
    assert answer.status == "insufficient_evidence"
    assert answer.answer == grounding.ABSTENTION
    assert captured == []


def test_model_abstention_uses_fixed_explanation(monkeypatch):
    answer, _ = run_reply(monkeypatch, json.dumps({"status": "insufficient_evidence", "answer": "Unsupported speculation", "evidence_quotes": []}))
    assert answer.answer == grounding.ABSTENTION


@pytest.mark.parametrize("reply", [
    "not JSON", "[]", "{}",
    '{"status":"answered","answer":"Claim","citation_ids":[]}',
    '{"status":"answered","answer":"Claim","citation_ids":["invented"]}',
    '{"status":"answered","answer":"Claim","citation_ids":["E1","E1"]}',
    '{"status":"answered","answer":"Claim","citation_ids":"E1"}',
    '{"status":"answered","answer":123,"citation_ids":["E1"]}',
    '{"status":"unknown","answer":"Claim","citation_ids":[]}',
    '{"status":"insufficient_evidence","answer":"Missing","citation_ids":["E1"]}',
    '{"status":"answered","answer":"Claim","citation_ids":["sound"]}',
])
def test_rejects_malformed_or_invalid_citations(monkeypatch, reply):
    with pytest.raises(ValueError):
        run_reply(monkeypatch, reply)


def test_http_error_is_preserved(monkeypatch):
    with pytest.raises(httpx.HTTPStatusError):
        run_reply(monkeypatch, "Unavailable", status_code=503)


@pytest.mark.parametrize("question", ["", " " * 3, "x" * 1001])
def test_invalid_question_rejected(monkeypatch, question):
    with pytest.raises(ValueError):
        run_reply(monkeypatch, "must not be used", question=question)


def test_exact_support_quote_selects_durable_id_in_code_and_keeps_ids_private():
    from dataclasses import replace
    first = RetrievalHit(replace(HIT.passage, passage_id='same_hash_prefix_001'), .9)
    second = RetrievalHit(replace(HIT.passage, passage_id='same_hash_prefix_002', text='The crew recorded a fan.'), .8)
    def handler(request):
        body = json.loads(request.content)
        assert 'citation_ids' not in body['format']['properties']
        prompt = body['messages'][0]['content']
        assert 'same_hash_prefix' not in prompt
        assert 'recorded a fan' in prompt
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'status': 'answered', 'answer': 'The crew recorded a fan.', 'evidence_quotes': ['The crew recorded a fan.']})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(handler)) as client:
            answer = await grounding.answer_from_hits(client, model='llama3.2:3b', question='How was sound made?', hits=[first, second])
            assert answer.citation_ids == ('same_hash_prefix_002',)
    asyncio.run(run())


@pytest.mark.parametrize('quotes,status', [
    ([], 'answered'), ([HIT.passage.text], 'insufficient_evidence'),
    (['An invented production fact not in the source.'], 'answered'),
    (['washing machine'], 'answered'), ([123], 'answered'),
])
def test_support_quotes_fail_closed_when_missing_fabricated_or_inconsistent(quotes, status):
    raw = json.dumps({'status': status, 'answer': 'A claim', 'evidence_quotes': quotes})
    with pytest.raises(ValueError): grounding._parse_supported_answer(raw, [HIT])


def test_repeated_valid_quotes_normalize_to_one_citation_and_trace():
    traces = []
    raw = json.dumps({'status': 'answered', 'answer': 'A washing machine.',
                     'evidence_quotes': [HIT.passage.text, HIT.passage.text]})
    answer = grounding._parse_supported_answer(raw, [HIT], on_trace=traces.append)
    assert answer.citation_ids == ('sound',)
    assert traces[0]['support'] == [{'passage_id': 'sound', 'quote': HIT.passage.text}]


@pytest.mark.parametrize('verdict,expected', [('supported','answered'),('unsupported','insufficient_evidence'),('uncertain','insufficient_evidence')])
def test_support_reviewer_gates_answer_and_emits_separate_trace(verdict, expected):
    # These fixtures isolate semantic gating from local model identity checks.
    # Identity verification has its own tests in test_background_fact_review.
    traces, calls = [], []
    def handler(request):
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':grounding.REVIEW_MODEL,'digest':DIGESTS[grounding.REVIEW_MODEL]}]})
        body=json.loads(request.content); calls.append(body['format'])
        result = ({'verdict':verdict,'reason':'Fixture support assessment','evidence_answer':'A washing machine.','evidence_quotes':[HIT.passage.text]} if 'verdict' in body['format']['properties']
                  else {'status':'answered','answer':'A washing machine.','evidence_quotes':[HIT.passage.text]})
        return httpx.Response(200,json={'message':{'content':json.dumps(result)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as client:
            result=await grounding.answer_from_hits(client,model='fixture',question='How?',hits=[HIT],verify_support=True,on_support_trace=traces.append)
            assert result.status==expected
            assert result.citation_ids == (('sound',) if expected=='answered' else ())
    asyncio.run(run())
    assert len(calls)==2
    assert traces[-1]['type']=='support_review'
    assert traces[-1]['verdict']==verdict


def test_abstention_skips_support_inference():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'message':{'content':json.dumps({'status':'insufficient_evidence','answer':'Missing','evidence_quotes':[]})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as client:
            await grounding.answer_from_hits(client,model='fixture',question='How?',hits=[HIT],verify_support=True)
    asyncio.run(run())
    assert len(calls)==1


def test_support_cancellation_propagates():
    async def handler(request):
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':grounding.REVIEW_MODEL,'digest':DIGESTS[grounding.REVIEW_MODEL]}]})
        if 'verdict' in json.loads(request.content)['format']['properties']:
            raise asyncio.CancelledError
        return httpx.Response(200,json={'message':{'content':json.dumps({'status':'answered','answer':'A washing machine.','evidence_quotes':[HIT.passage.text]})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(asyncio.CancelledError):
                await grounding.answer_from_hits(client,model='fixture',question='How?',hits=[HIT],verify_support=True)
    asyncio.run(run())


def test_identity_context_is_reviewed_and_cited_even_when_not_selected_by_generator():
    from movie_companion.discussion_context import SupportOption
    from movie_companion.retrieval_learning import EmbeddedPassage,RetrievalHit
    name='Linguist Mira Cole joins the expedition.'
    fact='Cole realizes her visions show future events.'
    hits=[RetrievalHit(EmbeddedPassage(i,155,text,[1.,0.],'fixture','Fixture','safe'),.9)
          for i,text in [('name',name),('fact',fact)]]
    options=[SupportOption(name,('name',),True),SupportOption(fact,('fact',))]
    traces=[]
    def handler(request):
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':grounding.REVIEW_MODEL,'digest':DIGESTS[grounding.REVIEW_MODEL]}]})
        body=json.loads(request.content)
        if 'verdict' in body['format']['properties']:
            prompt=body['messages'][0]['content'];assert name in prompt and fact in prompt
            result={'verdict':'supported','reason':'Name is connected.','evidence_answer':'Future visions.', 'evidence_quotes':[fact,name]}
        else:result={'status':'answered','answer':'Mira sees future events.','evidence_quotes':[fact]}
        return httpx.Response(200,json={'message':{'content':json.dumps(result)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as c:
            result=await grounding.answer_from_hits(c,model='fixture',question='What does Mira learn?',hits=hits,
                support_options=options,verify_support=True,on_support_trace=traces.append)
            assert result.citation_ids==('fact','name')
    asyncio.run(run())
    assert traces[-1]['identity_context']==[{'quote':name,'citation_ids':['name']}]


def test_identity_context_cannot_overflow_final_citation_budget():
    from movie_companion.discussion_context import SupportOption
    from movie_companion.retrieval_learning import EmbeddedPassage,RetrievalHit
    texts=['Linguist Mira Cole joins the expedition.', 'Cole reads the first message carefully.',
           'Cole sees a vision of the distant future.', 'Cole tells the captain about the visitors.']
    hits=[RetrievalHit(EmbeddedPassage(str(i),155,t,[1.,0.],'fixture','Fixture','safe'),.9) for i,t in enumerate(texts)]
    options=[SupportOption(t,(str(i),),i==0) for i,t in enumerate(texts)]
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        assert len(calls)==1  # No reviewer call after a citation-budget failure.
        return httpx.Response(200,json={'message':{'content':json.dumps({'status':'answered',
            'answer':'A proposed answer.','evidence_quotes':texts[1:]})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as c:
            result=await grounding.answer_from_hits(c,model='fixture',question='What does Mira learn?',hits=hits,
                support_options=options,verify_support=True)
            assert result.status=='insufficient_evidence' and result.citation_ids==()
    asyncio.run(run())


def test_supplemental_detail_is_exactly_reviewed_and_included_in_final_citations():
    from movie_companion.discussion_context import SupportOption
    from movie_companion.retrieval_learning import EmbeddedPassage,RetrievalHit
    generic='Cole learns the language changes her perception of time.'
    direct='Her visions are premonitions; her daughter will be born in the future.'
    hits=[RetrievalHit(EmbeddedPassage(i,155,t,[1.,0.],'fixture','Fixture','safe'),.9) for i,t in [('generic',generic),('direct',direct)]]
    options=[SupportOption(generic,('generic',)),SupportOption(direct,('direct',))]
    traces=[]
    def handler(request):
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':grounding.REVIEW_MODEL,'digest':DIGESTS[grounding.REVIEW_MODEL]}]})
        body=json.loads(request.content)
        if 'verdict' in body['format']['properties']:
            assert direct in body['messages'][0]['content']
            result={'verdict':'supported','reason':'Explicit future detail.','evidence_answer':'Future premonitions.', 'evidence_quotes':[direct]}
        else:result={'status':'answered','answer':'Her visions are premonitions and her daughter will be born in the future.','evidence_quotes':[generic]}
        return httpx.Response(200,json={'message':{'content':json.dumps(result)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as c:
            result=await grounding.answer_from_hits(c,model='fixture',question='What does Cole learn?',hits=hits,
                support_options=options,verify_support=True,on_support_trace=traces.append)
            assert result.citation_ids==('generic','direct')
    asyncio.run(run())
    assert traces[-1]['supplemental_context']=={'quote':direct,'citation_ids':['direct']}
