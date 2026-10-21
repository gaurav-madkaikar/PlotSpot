import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/review_provisional_quiz_replacements.py"
SPEC = importlib.util.spec_from_file_location("provisional_quiz_review", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def item(identifier, question, answer):
    return SimpleNamespace(
        id=identifier,
        question=question,
        options=[answer, "Second", "Third", "Fourth"],
        correct_index=0,
    )


def test_comparison_bank_excludes_only_the_question_being_replaced():
    quiz = SimpleNamespace(
        items=[
            item("replace-me", "Where is the meeting?", "In the basement"),
            item("keep-me", "Why do they meet?", "To regain control"),
        ]
    )

    existing, replaced = MODULE.comparison_bank(
        quiz, replaced_question_id="replace-me"
    )

    assert replaced == "Where is the meeting?"
    assert existing == [
        {"question": "Why do they meet?", "answer": "To regain control"}
    ]


def test_comparison_bank_rejects_a_stale_or_missing_target():
    quiz = SimpleNamespace(items=[item("other", "What changes?", "The plan")])

    with pytest.raises(ValueError, match="absent"):
        MODULE.comparison_bank(quiz, replaced_question_id="missing")


def test_frozen_packet_resolves_only_editorial_accepts():
    packet_path = (
        Path(__file__).resolve().parents[2]
        / "evals/movie-rag/quiz-narrative-quality/provisional-whole-bank-input-v1.json"
    )
    packet = json.loads(packet_path.read_text())

    candidates = [MODULE.load_candidate(selection)[0] for selection in packet["items"]]

    assert len(candidates) == 4
    assert all(candidate["question"] and len(candidate["options"]) == 4 for candidate in candidates)


def test_adjudication_context_is_released_as_data_not_prompt_authority():
    packet = {
        "source_report": "evals/movie-rag/quiz-narrative-quality/replacement-shaped-span-editorial-v1.json",
        "source_report_sha256": "0" * 64,
        "movie_id": 13,
        "question_id": "q-forrest",
        "candidate_sha256": "1" * 64,
        "adjudication_context": {
            "candidate_intent": "how Forrest's relationship changes when he becomes a father",
            "compared_bank_intent": "recall the name of Jenny's son",
            "decision_rule": MODULE.ADJUDICATION_RULE,
        },
    }

    normalized = MODULE.validate_selection(packet)

    assert normalized["adjudication_context"]["decision_rule"] == MODULE.ADJUDICATION_RULE


def test_uncertain_novelty_is_always_withheld():
    uncertain = SimpleNamespace(novelty="uncertain", clarity="clear")
    duplicate = SimpleNamespace(novelty="duplicate", clarity="clear")
    unclear = SimpleNamespace(novelty="new", clarity="needs_edit")
    ready = SimpleNamespace(novelty="new", clarity="clear")
    assert MODULE.ready_from_reviews([uncertain], None) is False
    assert MODULE.ready_from_reviews([duplicate], None) is False
    assert MODULE.ready_from_reviews([unclear], None) is False
    assert MODULE.ready_from_reviews([ready], "TimeoutError") is False
    assert MODULE.ready_from_reviews([ready], None) is True
