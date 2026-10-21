import asyncio
import json
from types import SimpleNamespace

import httpx

from movie_companion.movie_quiz import MovieQuiz, QuizItem
from movie_companion.movie_questions import QuestionCitation
from movie_companion.quiz_replacement_workflow import (
    ReplacementDraft, ReplacementDrafts, build_targets, deterministic_candidate_problems,
    generate_drafts, review_drafts,
)


def citation():
    return QuestionCitation(passage_id="p1", source_label="Example",
        source_ref="https://en.wikipedia.org/w/index.php?oldid=123456789",
        revision="enwiki-123456789-sections-v3-body",
        excerpt="After the flood destroys their home, the family must seek temporary shelter.")


def target():
    return {"evidence": {"citations": [citation().model_dump()]}, "remaining_questions": []}


def test_deterministic_replacement_requires_literal_answer_and_narrative_stem():
    useful = ReplacementDraft(target_id="T1",
        question="What consequence does the flood have for the family?",
        options=["the family must seek temporary shelter", "They inherit a mansion", "They leave the city", "They repair the house"],
        correct_index=0,
        evidence_quote="After the flood destroys their home, the family must seek temporary shelter.")
    assert deterministic_candidate_problems(useful, target()) == []

    granular = useful.model_copy(update={"question": "Where does the family seek shelter?",
                                         "options": ["A gymnasium", *useful.options[1:]]})
    assert deterministic_candidate_problems(granular, target()) == [
        "selected_answer_not_literal", "advisory_isolated_location"]


def test_build_targets_binds_review_to_current_saved_question():
    item = QuizItem(id="old", question="Where do they shelter?", options=["A gym", "A", "B", "C"],
                    correct_index=0, explanation=citation().excerpt, citations=[citation()])
    saved = {"quiz": MovieQuiz(status="ready", message="ready", items=[item]),
             "version": "v1", "prepared_at": "2026-01-01T00:00:00+00:00"}
    bank = SimpleNamespace(load=lambda movie_id: saved if movie_id == 1 else None)
    review = {"policy": "assistant-semantic-quiz-bank-review-v1", "status": "proposal_only",
              "summary": {"replace": 1}, "decisions": [{"movie_id": 1, "title": "Film",
              "question_id": "old", "question": "Where do they shelter?", "answer": "A gym",
              "disposition": "replace", "replacement_brief": "Test the flood's consequence.",
              "evidence": {"explanation": citation().excerpt,
                           "citations": [{k: getattr(citation(), k) for k in
                              ("source_label", "source_ref", "revision", "excerpt")}]} }]}
    targets = build_targets(review, bank)
    assert targets[0]["question_id"] == "old"
    assert targets[0]["remaining_questions"] == []


def test_writer_allows_explicit_abstention(monkeypatch):
    async def fake(*args, **kwargs):
        return json.dumps({"items": []})
    monkeypatch.setattr("movie_companion.ollama_learning.chat_once", fake)
    async def run():
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",
                                     follow_redirects=False) as client:
            return await generate_drafts(client, targets=[{
                "title": "Film", "old_question": "Where?", "replacement_brief": "Use broader evidence.",
                "evidence": {"citations": [citation().model_dump()]}, "remaining_questions": [],
            }])
    result = asyncio.run(run())
    assert result.items == []


def test_critic_repairs_a_malformed_multi_item_batch_one_at_a_time(monkeypatch):
    calls = []
    async def fake_review(client, *, model, proposals, evidence):
        calls.append(len(proposals.questions))
        if len(proposals.questions) > 1:
            raise ValueError("malformed batch")
        return SimpleNamespace(items=[SimpleNamespace(
            item_id="Q1", decision="accept", model_dump=lambda: {
                "item_id": "Q1", "decision": "accept", "reason": "supported",
                "assessment": None,
            })])
    monkeypatch.setattr("movie_companion.quiz_replacement_workflow.review_proposals", fake_review)
    drafts = ReplacementDrafts(items=[ReplacementDraft(target_id=f"T{i}",
        question="What consequence does the flood have for the family?",
        options=["the family must seek temporary shelter", "They inherit a mansion", "They leave the city", "They repair the house"],
        correct_index=0,
        evidence_quote="After the flood destroys their home, the family must seek temporary shelter.")
        for i in (1, 2)])
    async def run():
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",
                                     follow_redirects=False) as client:
            return await review_drafts(client, targets=[target(), target()], drafts=drafts)
    result = asyncio.run(run())
    assert calls == [2, 1, 1]
    assert all(item["ready_for_assistant_review"] for item in result)
