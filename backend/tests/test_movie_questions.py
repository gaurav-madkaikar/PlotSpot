import asyncio

from fastapi.testclient import TestClient
import httpx
import pytest

from movie_companion.evidence_store import SourceDocument
from movie_companion.grounding_learning import GroundedAnswer
from movie_companion.main import app, get_question_service
import movie_companion.movie_questions as qa
from movie_companion.retrieval_learning import EmbeddedPassage


SOURCE = SourceDocument("wiki-fixture", 157336, "Authored fixture source.", "Wikipedia fixture", "https://en.wikipedia.org/w/index.php?oldid=123", "fixture-v1", "unknown")
PASSAGE = EmbeddedPassage("fixture_001", 157336, SOURCE.text, [1.0, 0.5], "nomic-embed-text:v1.5", SOURCE.source_label, "unknown")


@pytest.fixture
def prepared_service(monkeypatch):
    calls = {"source": 0, "pipeline": 0}
    async def source(client, *, movie_id):
        calls["source"] += 1
        return SOURCE
    async def ingest(*args, **kwargs):
        return "cached"
    async def pipeline(client, **kwargs):
        calls["pipeline"] += 1
        assert kwargs["passages"] == [PASSAGE]
        return GroundedAnswer("answered", "An authored fixture answer.", (PASSAGE.passage_id,))
    class Store:
        def load_snapshot(self, *args, **kwargs):
            other = EmbeddedPassage("other", 202, "Other movie", [1.0, 0.5], PASSAGE.embedding_model, "Other", "safe")
            return [PASSAGE, other]
    monkeypatch.setattr(qa, "fetch_movie_source", source)
    monkeypatch.setattr(qa, "ingest_source", ingest)
    monkeypatch.setattr(qa, "answer_movie_question", pipeline)
    return qa.MovieQuestionService(None, None, store=Store()), calls


def test_spoiler_permission_and_coverage_precede_io(prepared_service):
    service, calls = prepared_service
    async def run():
        assert (await service.ask(157336, qa.MovieQuestion(question="A question"))).status == "spoiler_permission_required"
        assert (await service.ask(101, qa.MovieQuestion(question="A question", allow_spoilers=True))).status == "source_unavailable"
    asyncio.run(run())
    assert calls == {"source": 0, "pipeline": 0}


def test_scoped_pipeline_and_revision_citations(prepared_service):
    service, calls = prepared_service
    async def run():
        result = await service.ask(157336, qa.MovieQuestion(question="A question", allow_spoilers=True))
        assert result.citations[0].source_ref == SOURCE.source_ref
        assert result.citations[0].excerpt == SOURCE.text
        await service.ask(157336, qa.MovieQuestion(question="Another", allow_spoilers=True))
    asyncio.run(run())
    assert calls == {"source": 1, "pipeline": 2}


def test_pipeline_invented_citation_rejected(prepared_service, monkeypatch):
    service, _ = prepared_service
    async def bad(*args, **kwargs):
        return GroundedAnswer("answered", "Invented", ("other",))
    monkeypatch.setattr(qa, "answer_movie_question", bad)
    with pytest.raises(qa.QuestionError) as caught:
        asyncio.run(service.ask(157336, qa.MovieQuestion(question="Question", allow_spoilers=True)))
    assert caught.value.status == 502


def test_busy_request_is_recoverable(prepared_service):
    service, calls = prepared_service
    async def run():
        async with service.slot:
            with pytest.raises(qa.QuestionError) as caught:
                await service.ask(157336, qa.MovieQuestion(question="Question", allow_spoilers=True))
            assert caught.value.status == 409
    asyncio.run(run())
    assert calls["source"] == 0


@pytest.mark.parametrize("error, expected", [(NotImplementedError(), 503), (ValueError("private diagnostic"), 502), (httpx.ConnectError("private diagnostic"), 503)])
def test_pipeline_failures_sanitized(prepared_service, monkeypatch, error, expected):
    service, _ = prepared_service
    async def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(qa, "answer_movie_question", fail)
    with pytest.raises(qa.QuestionError) as caught:
        asyncio.run(service.ask(157336, qa.MovieQuestion(question="Question", allow_spoilers=True)))
    assert caught.value.status == expected
    assert "private diagnostic" not in str(caught.value)


@pytest.fixture
def endpoint_client(content_member, prepared_service):
    service, _ = prepared_service
    app.dependency_overrides[get_question_service] = lambda: service
    with content_member() as client:
        yield client
    app.dependency_overrides.pop(get_question_service, None)


def test_real_endpoint_contract(endpoint_client):
    reply = endpoint_client.post("/api/movies/157336/questions", json={"question": "Question", "allow_spoilers": True})
    assert reply.status_code == 200
    assert reply.json()["citations"][0]["passage_id"] == "fixture_001"


@pytest.mark.parametrize("body", [{"question": "  "}, {"question": "x" * 1001}, {"question": 123}, {"question": "Question", "allow_spoilers": "true"}])
def test_bad_question_inputs_rejected(endpoint_client, body):
    assert endpoint_client.post("/api/movies/157336/questions", json=body).status_code == 422


def test_reviewed_evidence_selection_preserves_source_citations(prepared_service):
    service, _ = prepared_service
    result = asyncio.run(service.ask(157336, qa.MovieQuestion(question="Question", allow_spoilers=True), evidence_phrase="AUTHORED FIXTURE"))
    assert result.citations[0].passage_id == PASSAGE.passage_id


def test_missing_reviewed_statement_cannot_fall_back_to_unrelated_evidence(prepared_service, monkeypatch):
    service, _ = prepared_service
    async def pipeline(client, **kwargs):
        assert kwargs["passages"] == []
        return GroundedAnswer("insufficient_evidence", "No evidence", ())
    monkeypatch.setattr(qa, "answer_movie_question", pipeline)
    result = asyncio.run(service.ask(157336, qa.MovieQuestion(question="Question", allow_spoilers=True), evidence_phrase="statement absent from source"))
    assert result.status == "insufficient_evidence"
    assert not result.citations


@pytest.mark.parametrize('purpose,category,eligible', [('story', 'plot', True), ('story', 'filming', False), ('background', 'music', True), ('background', 'plot', False), ('story', 'other', False)])
def test_internal_routing_filters_before_pipeline(prepared_service, monkeypatch, purpose, category, eligible):
    from dataclasses import replace
    service, _ = prepared_service
    passage = replace(PASSAGE, section_category=category)
    class Store:
        def load_snapshot(self, *args, **kwargs):
            return [passage]
    service.store = Store()
    async def pipeline(client, **kwargs):
        assert kwargs['passages'] == ([passage] if eligible else [])
        return GroundedAnswer('insufficient_evidence', 'No evidence', ())
    monkeypatch.setattr(qa, 'answer_movie_question', pipeline)
    asyncio.run(service.ask(157336, qa.MovieQuestion(question='Question', allow_spoilers=True), evidence_purpose=purpose))
