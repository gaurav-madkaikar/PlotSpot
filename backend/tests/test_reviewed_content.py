"""Contract/regression checks; authored fixtures are not a truth benchmark."""
import asyncio
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from movie_companion.content_store import ContentStore
from movie_companion.evidence_store import SourceDocument
from movie_companion.main import app, get_content_store, get_question_service
from movie_companion.prepared_content import compile_collection
from movie_companion.reviewed_content import load_bank
from movie_companion.source_sections import SourceSection
from movie_companion.wikipedia_source import MOVIE_ARTICLES

MOVIES = (27205, 329865, 603, 546554, 37165, 496243, 129, 120467, 438631, 155)


def source_fixture(movie):
    bank = load_bank(movie)
    story = '\n\n'.join('Fixture evidence: ' + '; '.join(e['evidence_markers']) + '.' for e in bank['quiz'])
    background = '\n\n'.join('Fixture evidence: ' + '; '.join(e['evidence_markers']) + '.' for e in bank['facts'])
    text = story + '\n\n' + background
    return SourceDocument('enwiki-123', movie, text,
        f'English Wikipedia contributors: {MOVIE_ARTICLES[movie]}',
        'https://en.wikipedia.org/w/index.php?oldid=123', 'enwiki-123-sections-v3-body', 'unknown',
        (SourceSection(0, len(story)+2, 'Plot', 'plot'),
         SourceSection(len(story)+2, len(text), 'Production', 'production')))


@pytest.mark.parametrize('movie', MOVIES)
def test_complete_unique_collection_and_durable_read(movie, tmp_path):
    source = source_fixture(movie)
    quiz, facts = compile_collection(source)
    assert len(quiz.items) == 10 and len(facts.items) == 5
    assert quiz.can_generate_more is False
    assert all(q.kind != 'interpretation' and q.origin == 'reviewed' for q in quiz.items)
    for item in [*quiz.items, *facts.items]:
        assert 20 <= len(item.citations[0].excerpt) <= 600
        assert item.citations[0].excerpt in source.text
        assert item.citations[0].source_ref == source.source_ref
    store = ContentStore(tmp_path/'content.db')
    store.publish(movie, version='test', source_revision=source.revision, quiz=quiz, facts=facts)
    assert ContentStore(store.path).load(movie)['quiz'] == quiz
    assert compile_collection(source)[0] == quiz  # stable citations


@pytest.mark.parametrize('failure', ['missing', 'swapped-sections', 'title', 'revision', 'unclassified', 'unsupported'])
def test_ineligible_source_cannot_replace_collection(failure, tmp_path):
    source = source_fixture(27205)
    quiz, facts = compile_collection(source)
    store = ContentStore(tmp_path/'content.db')
    store.publish(27205, version='original', source_revision=source.revision, quiz=quiz, facts=facts)
    before = store.load(27205)
    if failure == 'missing':
        marker = 'implanting Robert Fischer'
        source = replace(source, text=source.text.replace(marker, 'x' * len(marker)))
    elif failure == 'swapped-sections':
        source = replace(source, sections=tuple(replace(s, category='production' if s.category=='plot' else 'plot') for s in source.sections))
    elif failure == 'title': source = replace(source, source_label='English Wikipedia contributors: The Matrix')
    elif failure == 'revision': source = replace(source, revision='enwiki-456-sections-v3-body')
    elif failure == 'unclassified': source = replace(source, sections=())
    else: source = replace(source, movie_id=999)
    with pytest.raises(ValueError):
        new_quiz, new_facts = compile_collection(source)
        store.publish(27205, version='new', source_revision=source.revision, quiz=new_quiz, facts=new_facts)
    assert store.load(27205) == before


def prepare_module():
    script = Path(__file__).resolve().parents[1]/'scripts/prepare_movie_content.py'
    spec = importlib.util.spec_from_file_location('multi_prepare_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_preparation_retains_publication_without_source_io(tmp_path, monkeypatch):
    module = prepare_module()
    source = source_fixture(329865)
    snapshot = tmp_path/'source.json'; snapshot.write_text(json.dumps(asdict(source)))
    args = SimpleNamespace(movie_id=329865, database=tmp_path/'content.db', source_snapshot=snapshot,
                           refresh=False, report=tmp_path/'report.json')
    async def forbidden(*a, **k): pytest.fail('Snapshot preparation must not fetch')
    monkeypatch.setattr(module, 'fetch_movie_source', forbidden)
    asyncio.run(module.prepare(args))
    assert json.loads(args.report.read_text())['state'] == 'published'
    before = ContentStore(args.database).load(329865)
    args.source_snapshot = tmp_path/'missing.json'
    asyncio.run(module.prepare(args))
    assert ContentStore(args.database).load(329865) == before
    assert json.loads(args.report.read_text())['state'] == 'retained'
    args.refresh = True
    with pytest.raises(FileNotFoundError): asyncio.run(module.prepare(args))
    assert ContentStore(args.database).load(329865) == before


def test_snapshot_movie_identity_mismatch_is_rejected(tmp_path):
    module = prepare_module()
    snapshot = tmp_path/'source.json'; snapshot.write_text(json.dumps(asdict(source_fixture(603))))
    args = SimpleNamespace(movie_id=27205, database=tmp_path/'content.db', source_snapshot=snapshot, refresh=False)
    with pytest.raises(ValueError, match='different movie'): asyncio.run(module.prepare(args))
    assert ContentStore(args.database).load(27205) is None


@pytest.mark.parametrize('movie', [546554, 37165, 496243, 129, 120467, 438631, 155])
@pytest.mark.parametrize('failure', ['missing-story', 'missing-background', 'wrong-film'])
def test_added_movie_requires_both_evidence_branches(movie, failure, tmp_path):
    source = source_fixture(movie)
    quiz, facts = compile_collection(source)
    store = ContentStore(tmp_path/'content.db')
    store.publish(movie, version='original', source_revision=source.revision, quiz=quiz, facts=facts)
    before = store.load(movie)
    if failure == 'wrong-film':
        source = replace(source, source_label='English Wikipedia contributors: Inception')
    else:
        branch = 'quiz' if failure == 'missing-story' else 'facts'
        marker = load_bank(movie)[branch][0]['evidence_markers'][0]
        source = replace(source, text=source.text.replace(marker, 'x' * len(marker)))
    with pytest.raises(ValueError):
        compile_collection(source)
    assert store.load(movie) == before


@pytest.mark.parametrize('sentence', [
    'Leto meets Stilgar and Dr. Liet Kynes, a planetologist who lives among the Fremen.',
    'The role was developed by David J. Peterson, the language creator.',
])
def test_reviewed_citation_does_not_end_at_honorific_or_initial(sentence, monkeypatch):
    # Exercise the actual citation compiler, not a standalone tokenization mirror.
    from movie_companion import reviewed_content
    bank = load_bank(438631)
    bank['quiz'][0]['evidence_markers'] = ['Leto meets' if sentence.startswith('Leto') else 'David']
    original = source_fixture(438631)
    text = sentence + '\n\n' + original.text
    source = replace(original, text=text, sections=(
        SourceSection(0, len(sentence)+2, 'Plot', 'plot'),
        *[replace(s, start=s.start+len(sentence)+2, end=s.end+len(sentence)+2) for s in original.sections],
    ))
    monkeypatch.setattr(reviewed_content, 'load_bank', lambda movie: bank)
    quiz, _ = compile_collection(source)
    assert quiz.items[0].citations[0].excerpt == sentence


@pytest.mark.parametrize('movie', MOVIES)
def test_saved_features_and_reads_without_model_service(content_member, movie, tmp_path, monkeypatch):
    from movie_companion.story_rag import StoryRag
    monkeypatch.setattr(StoryRag, 'quiz_enabled', lambda self, movie_id: False)
    source = source_fixture(movie); quiz, facts = compile_collection(source)
    store = ContentStore(tmp_path/'content.db')
    store.publish(movie, version='test', source_revision=source.revision, quiz=quiz, facts=facts)
    def forbidden(): pytest.fail('Saved reads must not construct the AI service')
    app.dependency_overrides[get_content_store] = lambda: store
    app.dependency_overrides[get_question_service] = forbidden
    try:
        with content_member() as client:
            inventory = client.get(f'/api/movies/{movie}/features').json()
            assert inventory['facts'] and inventory['quiz'] and inventory['discussion']
            for kind, count in [('quiz',10), ('facts',5)]:
                assert client.get(f'/api/movies/{movie}/{kind}').json()['items'] == []
                first = client.get(f'/api/movies/{movie}/{kind}?allow_spoilers=true').json()
                assert len(first['items']) == count
                assert client.get(f'/api/movies/{movie}/{kind}?allow_spoilers=true').json() == first
                if kind == 'quiz': assert first['can_generate_more'] is False
    finally:
        app.dependency_overrides.pop(get_content_store, None)
        app.dependency_overrides.pop(get_question_service, None)
