import pytest
from fastapi.testclient import TestClient
from movie_companion.content_store import ContentStore
from movie_companion.evidence_store import SourceDocument
from movie_companion.source_sections import SourceSection
from movie_companion.prepared_content import BANK, PRODUCTION, STORY_EXTRA, FACT_EXTRA, compile_collection
from movie_companion.main import app, get_content_store, get_question_service


def fixture_collection():
    story = '\n\n'.join('Authored fixture: ' + e['source_phrase'] + ' ' + e['fact'] + '.' for e in [*BANK, *STORY_EXTRA])
    story += '\n\nAuthored extra scene: Doyle was killed by a wave. Another event cost 51 years. The cargo was 5,000 frozen embryos.'
    background = '\n\n'.join('Authored fixture: ' + e['source_phrase'] + ' ' + e['fact'] + '.' for e in [*PRODUCTION, *FACT_EXTRA])
    text = story + '\n\n' + background
    sections = (SourceSection(0, len(story) + 2, 'Plot', 'plot'), SourceSection(len(story) + 2, len(text), 'Production', 'production'))
    source = SourceDocument('fixture', 157336, text, 'Wikipedia fixture', 'https://en.wikipedia.org/w/index.php?oldid=123', 'fixture-rev', 'unknown', sections)
    return source, compile_collection(source)


def test_complete_collection_survives_store_restart(tmp_path):
    source, (quiz, facts) = fixture_collection()
    path = tmp_path / 'content.db'
    ContentStore(path).publish(157336, version='v1', source_revision=source.revision, quiz=quiz, facts=facts)
    saved = ContentStore(path).load(157336)
    assert len(saved['facts'].items) == 5
    assert len([q for q in saved['quiz'].items if q.kind != 'interpretation']) == 10
    assert saved['prepared_at'] and saved['version'] == 'v1'
    assert ContentStore(path).load(99) is None


@pytest.mark.parametrize('failure', ['too-few-questions', 'too-few-facts', 'duplicate-question', 'duplicate-fact', 'wrong-revision'])
def test_failed_refresh_preserves_published_collection(tmp_path, failure):
    source, (quiz, facts) = fixture_collection()
    store = ContentStore(tmp_path / 'content.db')
    store.publish(157336, version='v1', source_revision=source.revision, quiz=quiz, facts=facts)
    original = store.load(157336)
    if failure == 'too-few-questions': quiz.items = quiz.items[:9]
    if failure == 'too-few-facts': facts.items = facts.items[:4]
    if failure == 'duplicate-question': quiz.items[1] = quiz.items[0]
    if failure == 'duplicate-fact': facts.items[1] = facts.items[0]
    with pytest.raises(ValueError):
        store.publish(157336, version='v2', source_revision='wrong' if failure == 'wrong-revision' else source.revision, quiz=quiz, facts=facts)
    assert store.load(157336) == original


def test_compiler_rejects_missing_statement_and_wrong_movie():
    source, _ = fixture_collection()
    from dataclasses import replace
    with pytest.raises(ValueError): compile_collection(replace(source, text='Unrelated source', sections=()))
    with pytest.raises(ValueError): compile_collection(replace(source, movie_id=99))


def test_saved_endpoints_do_not_generate_and_gate_spoilers(content_member, tmp_path):
    source, (quiz, facts) = fixture_collection()
    store = ContentStore(tmp_path / 'content.db')
    store.publish(157336, version='v1', source_revision=source.revision, quiz=quiz, facts=facts)
    def forbidden(): raise AssertionError('Reading saved content must not depend on the question service')
    app.dependency_overrides[get_content_store] = lambda: store
    app.dependency_overrides[get_question_service] = forbidden
    try:
        with content_member() as client:
            for kind, count in [('quiz', 11), ('facts', 5)]:
                assert client.get(f'/api/movies/157336/{kind}').json()['items'] == []
                url = f'/api/movies/157336/{kind}?allow_spoilers=true'
                first = client.get(url)
                assert first.status_code == 200
                assert len(first.json()['items']) == count
                assert first.json()['content_version'] == 'v1'
                assert client.get(url).json() == first.json()
                assert client.post(f'/api/movies/157336/{kind}', json={'allow_spoilers': True}).json() == first.json()
                assert client.get(f'/api/movies/99/{kind}?allow_spoilers=true').json()['status'] == 'source_unavailable'
            assert client.post('/api/movies/157336/quiz', json={'allow_spoilers':'yes'}).status_code == 422
    finally:
        app.dependency_overrides.pop(get_content_store, None)
        app.dependency_overrides.pop(get_question_service, None)


def test_prepare_retains_older_published_version_without_fetching(tmp_path, monkeypatch, capsys):
    import asyncio
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    script = Path(__file__).resolve().parents[1] / 'scripts/prepare_movie_content.py'
    spec = importlib.util.spec_from_file_location('prepare_content_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, (quiz, facts) = fixture_collection()
    path = tmp_path / 'content.db'
    store = ContentStore(path)
    store.publish(157336, version='older-published-version', source_revision=source.revision, quiz=quiz, facts=facts)
    before = store.load(157336)
    async def forbidden(*args, **kwargs):
        pytest.fail('Preparation must not fetch when a published collection already exists')
    monkeypatch.setattr(module, 'fetch_movie_source', forbidden)
    asyncio.run(module.prepare(SimpleNamespace(database=path, refresh=False, source_snapshot=None)))
    assert store.load(157336) == before
    assert 'retained' in capsys.readouterr().out
