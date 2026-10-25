from dataclasses import replace
import asyncio
import json
from fastapi.testclient import TestClient
import pytest

from movie_companion.content_store import ContentStore
from movie_companion.main import app, get_content_store, get_question_service
from movie_companion.movie_features import movie_features
from movie_companion.movie_questions import MovieQuestion, MovieQuestionService
import movie_companion.movie_questions as qa
from movie_companion.grounding_learning import GroundedAnswer
from movie_companion.evidence_store import SourceDocument
from movie_companion.retrieval_learning import EmbeddedPassage
from movie_companion.wikipedia_source import MOVIE_ARTICLES, map_article_response
from test_content_store import fixture_collection


def test_inventory_uses_sources_and_published_content_independently(tmp_path):
    store = ContentStore(tmp_path/'content.db')
    assert movie_features(329865, store).model_dump() == {'movie_id':329865,'discussion':True,'quiz':False,'facts':False}
    assert not movie_features(999999, store).discussion
    source, (quiz, facts) = fixture_collection()
    store.publish(157336,version='v1',source_revision=source.revision,quiz=quiz,facts=facts)
    assert movie_features(157336, store).quiz
    assert movie_features(157336, store).facts
    assert MOVIE_ARTICLES[155] == 'The Dark Knight'
    assert movie_features(155, store).discussion
    assert not movie_features(155, store).quiz  # Registration alone is not publication.


def test_inventory_endpoint_does_not_call_source_or_model(content_member, tmp_path):
    app.dependency_overrides[get_content_store] = lambda: ContentStore(tmp_path/'content.db')
    def forbidden(): pytest.fail('Inventory must not use source/model service')
    app.dependency_overrides[get_question_service] = forbidden
    try:
        with content_member() as client:
            data = client.get('/api/movies/329865/features').json()
            assert data['movie_id'] == 329865 and data['discussion'] and not data['quiz']
            assert client.get('/api/movies/0/features').status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_inventory_error_is_sanitized(content_member):
    class Store:
        def load(self, movie_id): raise ValueError('private store detail')
    app.dependency_overrides[get_content_store] = lambda: Store()
    try:
        with content_member() as client:
            response = client.get('/api/movies/329865/features')
            assert response.status_code == 503
            assert 'private' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_sources_and_retrieval_remain_isolated_and_cache_multiple_movies(monkeypatch):
    calls, retrieved = [], []
    sources = {mid: SourceDocument(f's{mid}', mid, f'Authored evidence for movie {mid}.', 'Wikipedia fixture', f'https://en.wikipedia.org/w/index.php?oldid={mid}', f'rev{mid}') for mid in [157336,329865]}
    async def fetch(client, *, movie_id):
        calls.append(movie_id)
        return sources[movie_id]
    async def ingest(*args, **kwargs): return 'cached'
    class Store:
        def load_snapshot(self, source, **kwargs):
            return [EmbeddedPassage(f'p{mid}',mid,s.text,[1.,.5],'nomic-embed-text:v1.5','Wikipedia fixture') for mid,s in sources.items()]
    async def pipeline(client, **kwargs):
        assert [p.movie_id for p in kwargs['passages']] == [kwargs['movie_id']]
        retrieved.append(kwargs['movie_id'])
        return GroundedAnswer('answered','Authored evidence answer.',(kwargs['passages'][0].passage_id,))
    monkeypatch.setattr(qa,'fetch_movie_source',fetch)
    monkeypatch.setattr(qa,'ingest_source',ingest)
    monkeypatch.setattr(qa,'answer_movie_question',pipeline)
    service=MovieQuestionService(None,None,store=Store())
    async def run():
        # Consent applies to every mapped movie and precedes all source/model I/O.
        assert (await service.ask(329865,MovieQuestion(question='A question'))).status=='spoiler_permission_required'
        assert not calls
        for mid in [157336,329865,157336]:
            result=await service.ask(mid,MovieQuestion(question='A question',allow_spoilers=True))
            assert result.citations[0].source_ref == sources[mid].source_ref
            assert result.citations[0].excerpt == sources[mid].text
        service.source_cache[329865]=(0,sources[329865])
        await service.ask(329865,MovieQuestion(question='A question',allow_spoilers=True))
    asyncio.run(run())
    assert calls == [157336,329865,329865]
    assert retrieved == [157336,329865,157336,329865]


def test_reference_lists_are_removed_at_section_boundary():
    payload={'parse':{'title':'Arrival (film)','pageid':1,'revid':2,'text':'<p>Intro.</p><h2>Plot</h2><p>A story.</p><h2>References</h2><p>'+('X'*100001)+'</p>'}}
    source=map_article_response(payload,movie_id=329865,expected_title='Arrival (film)')
    assert 'A story.' in source.text and 'References' not in source.text and 'X' not in source.text
    assert source.sections[-1].category == 'plot'
