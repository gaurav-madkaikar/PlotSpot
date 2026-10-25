import asyncio
import json
from types import SimpleNamespace
import pytest
from movie_companion.content_store import ContentStore
from movie_companion.movie_questions import QuestionError
from movie_companion.movie_quiz import MovieQuiz
import movie_companion.quiz_generation as gen
from test_content_store import fixture_collection


def proposal(quiz):
    c = quiz.items[0].citations[0]
    return dict(question='Which kind of code is visible in the mysterious dust patterns?', options=['binary', 'decimal', 'hexadecimal', 'alphabetic'], correct_index=0, passage_id=c.passage_id, evidence_quote=c.excerpt)


def test_accepts_exact_support_and_rejects_invented_evidence():
    _, (quiz, _) = fixture_collection()
    p = proposal(quiz)
    assert len(gen.accept_proposals(json.dumps({'questions':[p]}), quiz)) == 1
    for patch in [{'passage_id':'invented'}, {'evidence_quote':'Invented statement with binary code'}, {'question':quiz.items[0].question}, {'options':['binary']*4}, {'options':['unicorn','decimal','hexadecimal','alphabetic']}]:
        assert gen.accept_proposals(json.dumps({'questions':[{**p, **patch}]}), quiz) == []


def test_duplicate_batch_question_is_not_added_twice():
    _, (quiz, _) = fixture_collection()
    p = proposal(quiz)
    assert len(gen.accept_proposals(json.dumps({'questions':[p,p]}), quiz)) == 1


@pytest.mark.parametrize("mixed_sources", [False, True])
def test_generation_persists_only_accepted_items(tmp_path, monkeypatch, mixed_sources):
    source, (quiz,facts) = fixture_collection()
    store=ContentStore(tmp_path/'content.db')
    if mixed_sources:
        from test_external_sources import article
        from movie_companion.external_content import compile_external_fact
        facts.items.append(compile_external_fact(article()))
    manifest = {c.revision: c.source_ref for item in [*quiz.items, *facts.items] for c in item.citations}
    store.publish(157336,version='v1',source_revision=source.revision,source_manifest=manifest,quiz=quiz,facts=facts)
    async def fake(*args, **kwargs):
        target = json.loads(kwargs['prompt'][kwargs['prompt'].index('{"targets"'):])['targets'][0]
        return json.dumps({'questions':[dict(question='Which person was killed by the wave in the supplied scene?', options=[target['target_answer'],'Another person','A robot','Nobody'], correct_index=0, passage_id=target['passage_id'], evidence_quote=target['sentence'])]})
    monkeypatch.setattr(gen,'chat_once',fake)
    service=SimpleNamespace(slot=asyncio.Lock(),ollama=None,chat_model='local')
    result=asyncio.run(gen.generate_more(service,store,movie_id=157336,allow_spoilers=True))
    assert len(result.items)==12
    assert result.items[-2].origin=='generated'
    assert len(ContentStore(tmp_path/'content.db').load(157336)['quiz'].items)==12
    assert result.items[-1].kind=='interpretation'
    saved = store.load(157336)
    assert saved['source_manifest'] == manifest
    assert saved['facts'] == facts


def test_generation_permission_and_failure_preserve_saved_collection(tmp_path, monkeypatch):
    source,(quiz,facts)=fixture_collection();store=ContentStore(tmp_path/'content.db')
    store.publish(157336,version='v1',source_revision=source.revision,quiz=quiz,facts=facts)
    original=store.load(157336)
    service=SimpleNamespace(slot=asyncio.Lock(),ollama=None,chat_model='local')
    assert asyncio.run(gen.generate_more(service,store,movie_id=157336,allow_spoilers=False)).status=='spoiler_permission_required'
    async def fake(*args, **kwargs): return json.dumps({'questions':[{**proposal(quiz),'passage_id':'invented'}]})
    monkeypatch.setattr(gen,'chat_once',fake)
    with pytest.raises(QuestionError): asyncio.run(gen.generate_more(service,store,movie_id=157336,allow_spoilers=True))
    assert store.load(157336)==original


def test_stale_generation_cannot_overwrite_newer_collection(tmp_path):
    source,(quiz,facts)=fixture_collection();store=ContentStore(tmp_path/'content.db')
    store.publish(157336,version='v1',source_revision=source.revision,quiz=quiz,facts=facts)
    with pytest.raises(ValueError): store.publish(157336,version='v2',source_revision=source.revision,quiz=quiz,facts=facts,expected_prepared_at='stale')
    assert store.load(157336)['version']=='v1'


def test_target_selection_uses_complete_matching_sentence():
    _, (quiz, _) = fixture_collection()
    citation = quiz.items[0].citations[0].model_copy(update={'passage_id':'target', 'excerpt':'y, and Doyle traverses the wormhole. A gigantic tidal wave kills Doyle.'})
    quiz.items[0] = quiz.items[0].model_copy(update={'citations':[citation]})
    _, targets = gen.select_targets(quiz)
    assert targets['P1']['sentence'] == 'A gigantic tidal wave kills Doyle.'


def test_state_cannot_be_presented_as_awakening_cause():
    _, (quiz, _) = fixture_collection()
    citation = quiz.items[0].citations[0].model_copy(update={'excerpt':'On the planet they awaken Mann from cryostasis.'})
    p = dict(question='What is used to awaken Mann?', options=['cryostasis','fire','water','gravity'], correct_index=0, passage_id='P1', evidence_quote=citation.excerpt)
    assert gen.accept_proposals(json.dumps({'questions':[p]}),quiz,evidence_override={'P1':citation},targets={'P1':{'id':'mann-awakening','answer':'cryostasis'}}) == []
