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
