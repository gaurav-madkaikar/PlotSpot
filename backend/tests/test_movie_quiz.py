import asyncio

from fastapi.testclient import TestClient
import pytest

from movie_companion.main import app, get_question_service
from movie_companion.movie_quiz import BANK, create_quiz
from movie_companion.movie_facts import PRODUCTION, create_facts
from movie_companion.movie_questions import MovieAnswer, QuestionCitation, QuestionError


class Service:
    def __init__(self, mode="ready"):
        self.calls = 0
        self.mode = mode

    async def ask(self, movie_id, request, *, evidence_phrase=None, evidence_purpose=None):
        assert evidence_purpose in {"story", "background"}
        self.calls += 1
        if not request.allow_spoilers:
            return MovieAnswer(status="spoiler_permission_required", answer="Allow spoilers")
        if movie_id != 157336:
            return MovieAnswer(status="source_unavailable", answer="Unavailable")
        if self.mode == "partial" and self.calls == 2:
            raise QuestionError(503, "Unavailable")
        entry = next(entry for entry in (*BANK, *PRODUCTION) if entry.get("evidence_question", entry["question"]) == request.question)
        index = self.calls
        text = f"Authored fixture: {entry['fact']} {entry['source_phrase']}"
        if self.mode == "unrelated":
            text = "Unrelated evidence from the film"
        citation = QuestionCitation(passage_id=f"fixture_{index}", source_label="Wikipedia fixture", source_ref="https://en.wikipedia.org/w/index.php?oldid=123", revision="fixture", excerpt=text)
        return MovieAnswer(status="answered", answer=entry["fact"], citations=[citation])


def test_quiz_has_supported_answers_and_sources():
    service = Service()
    quiz = asyncio.run(create_quiz(service, movie_id=157336, allow_spoilers=True))
    assert quiz.status == "ready"
    assert len(quiz.items) == 4
    assert quiz.items[0].options[quiz.items[0].correct_index] == "A secret NASA facility"
    assert quiz.items[1].options[quiz.items[1].correct_index] == "In the hope of being rescued"
    assert quiz.items[2].kind == "ending"
    assert quiz.items[3].kind == "interpretation"
    assert "not a confirmed hidden message" in quiz.items[3].explanation
    assert service.calls == 3


@pytest.mark.parametrize("movie_id,permission,status", [(157336, False, "spoiler_permission_required"), (101, True, "source_unavailable")])
def test_permission_and_source_unavailable_do_not_create_questions(movie_id, permission, status):
    quiz = asyncio.run(create_quiz(Service(), movie_id=movie_id, allow_spoilers=permission))
    assert quiz.status == status
    assert not quiz.items


def test_partial_failure_preserves_verified_item():
    quiz = asyncio.run(create_quiz(Service("partial"), movie_id=157336, allow_spoilers=True))
    assert len(quiz.items) == 1


def test_unrelated_cited_text_cannot_validate_quiz_answer():
    with pytest.raises(QuestionError) as error:
        asyncio.run(create_quiz(Service("unrelated"), movie_id=157336, allow_spoilers=True))
    assert error.value.status == 502


def test_production_background_is_available_as_facts():
    result = asyncio.run(create_facts(Service(), movie_id=157336, allow_spoilers=True))
    assert result.status == "ready"
    assert [item.id for item in result.items] == ["real-cornfield", "secret-title"]
    assert "500" in result.items[0].text
    assert "secret name" in result.items[1].text
    assert all("composer" != item["id"] for item in BANK)
