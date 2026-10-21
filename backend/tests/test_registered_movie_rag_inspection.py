"""Frozen-label setup checks; no model-quality claim is made by these fixtures."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import asyncio
import httpx

import pytest

from movie_companion.evidence_store import snapshot_key
from movie_companion.retrieval_learning import EmbeddedPassage
from test_reviewed_content import source_fixture


def runner():
    path = Path(__file__).resolve().parents[1]/'scripts/evaluate_registered_movie_rag.py'
    spec = importlib.util.spec_from_file_location('registered_rag_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure', ['changed-source', 'unknown-passage', 'overwrite', 'wrong-title'])
def test_labels_and_movie_identity_are_validated_before_model_io(tmp_path, failure):
    module = runner()
    source = source_fixture(155)
    key = snapshot_key(source, model=module.EMBEDDING_MODEL, **module.CHUNK_SETTINGS)
    snapshot = tmp_path/'source.json'
    data = asdict(source)
    labels = {'version': 'fixture-dev-v1', 'split': 'development', 'source_snapshot': key,
              'cases': [{'id': 'example', 'question': 'A labelled question?', 'expected_status': 'answered',
                         'relevant_passage_ids': [f'{key[:32]}_000'], 'required_phrase_groups': [['example']]}]}
    if failure == 'changed-source': data['text'] = data['text'].replace('Fixture', 'fixture', 1)
    if failure == 'unknown-passage': labels['cases'][0]['relevant_passage_ids'] = ['not-in-snapshot']
    if failure == 'wrong-title': data['source_label'] = 'English Wikipedia contributors: Inception'
    snapshot.write_text(json.dumps(data))
    dataset = tmp_path/'cases.json'; dataset.write_text(json.dumps(labels))
    output = snapshot if failure == 'overwrite' else tmp_path/'report.json'
    args = SimpleNamespace(source_snapshot=snapshot, dataset=dataset, output=output)
    before = snapshot.read_bytes(), dataset.read_bytes()
    with pytest.raises(ValueError): module.load_inputs(args)
    assert (snapshot.read_bytes(), dataset.read_bytes()) == before
    assert not (tmp_path/'report.json').exists()


def test_frozen_baseline_keeps_original_prompt_ids_and_vector_only_ranking():
    module = runner()
    baseline = module.frozen_vector_baseline()
    calls, observed = [], []
    model = 'nomic-embed-text:v1.5'
    theme = EmbeddedPassage('theme', 155, 'The detective represents moral authority.', [1., 0.], model, 'Fixture', 'safe', 'Themes', 'other')
    event = EmbeddedPassage('event', 155, 'The detective claims to be the thief to lure a rival.', [0., 1.], model, 'Fixture', 'safe', 'Plot', 'plot')
    def handler(request):
        calls.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path == '/api/embed':
            return httpx.Response(200, json={'embeddings': [[1., 0.]]})
        assert body['format']['properties']['citation_ids']['items']['enum'] == ['event', 'theme']
        assert 'Choose the smallest set of citations' not in body['messages'][0]['content']
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'status': 'insufficient_evidence', 'answer': 'Missing', 'citation_ids': []})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://local', transport=httpx.MockTransport(handler)) as client:
            answer = await baseline(client, question='Why does the detective claim to be the thief?',
                passages=[event, theme], movie_id=155, allow_spoilers=True,
                embedding_model=model, chat_model='llama3.2:3b', on_retrieved=observed.extend)
            assert answer.status == 'insufficient_evidence'
    asyncio.run(run())
    assert calls == ['/api/embed', '/api/chat']
    assert [h.passage.passage_id for h in observed] == ['theme', 'event']


def test_frozen_current_baseline_keeps_one_chat_call_and_original_options():
    baseline=runner().frozen_hybrid_baseline()
    calls=[]
    passage=EmbeddedPassage('fixture',155,'The crew recorded a washing machine.',[1.,0.],'fixture','Fixture','safe')
    def handler(request):
        calls.append(request.url.path)
        body=json.loads(request.content)
        if request.url.path=='/api/embed':return httpx.Response(200,json={'embeddings':[[1.,0.]]})
        assert 'verdict' not in body['format']['properties']
        return httpx.Response(200,json={'message':{'content':json.dumps({'status':'answered','answer':'A washing machine.','evidence_quotes':[passage.text]})}})
    async def run():
        async with httpx.AsyncClient(base_url='http://fixture',transport=httpx.MockTransport(handler)) as client:
            result=await baseline(client,question='How was sound recorded?',passages=[passage],movie_id=155,allow_spoilers=False,embedding_model='fixture',chat_model='fixture')
            assert result.citation_ids==('fixture',)
    asyncio.run(run())
    assert calls==['/api/embed','/api/chat']


def test_support_baseline_keeps_old_reviewer_contract_without_identity_context():
    baseline=runner().frozen_support_baseline()
    text='The crew recorded a washing machine.'
    passage=EmbeddedPassage('fixture',155,text,[1.,0.],'fixture','Fixture','safe')
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path=='/api/embed':return httpx.Response(200,json={'embeddings':[[1.,0.]]})
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':'qwen3.5:9b','digest':DIGESTS['qwen3.5:9b']}]})
        body=json.loads(request.content)
        if 'verdict' in body['format']['properties']:
            assert set(body['format']['properties'])=={'verdict','reason'}
            assert body['options']['num_predict']==512
            result={'verdict':'supported','reason':'Old reviewer fixture.'}
        else:result={'status':'answered','answer':'A washing machine.','evidence_quotes':[text]}
        return httpx.Response(200,json={'message':{'content':json.dumps(result)}})
    async def run():
        async with httpx.AsyncClient(base_url='http://local',transport=httpx.MockTransport(handler)) as c:
            result=await baseline(c,question='How was sound made?',passages=[passage],movie_id=155,
                allow_spoilers=True,embedding_model='fixture',chat_model='fixture')
            assert result.status=='answered'
    asyncio.run(run())
    assert calls==['/api/embed','/api/chat','/api/tags','/api/chat']
