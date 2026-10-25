import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/assemble_quiz_replacement_completion.py"
)
SPEC = importlib.util.spec_from_file_location("quiz_completion_assembler", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def original_review():
    return {
        "decisions": [
            {
                "movie_id": index + 1,
                "question_id": f"q{index}",
                "disposition": "replace",
            }
            for index in range(34)
        ]
    }


def decisions():
    return [
        {
            "movie_id": index + 1,
            "question_id": f"q{index}",
            "lane": "existing_ready" if index < 3 else "intent",
            "decision": "ready" if index < 3 else "withheld",
            "withheld_reason": None if index < 3 else "quality_gate_not_passed",
        }
        for index in range(34)
    ]


def test_final_report_accounts_for_every_original_replacement_once():
    rows = decisions()
    MODULE.exact_scope(original_review(), rows)
    report = MODULE.build_final_report(rows, {"manifest": "0" * 64})
    identities = [
        (row["movie_id"], row["question_id"]) for row in report["items"]
    ]
    assert len(identities) == len(set(identities)) == 34
    assert report["summary"]["ready"] + report["summary"]["withheld"] == 34
    assert all(row["decision"] in ("ready", "withheld") for row in report["items"])


def test_complete_scope_rejects_duplicate_or_missing_target():
    rows = decisions()
    rows[-1] = rows[0]
    with pytest.raises(ValueError, match="original scope"):
        MODULE.exact_scope(original_review(), rows)


def test_stale_candidate_or_bank_hash_is_rejected():
    with pytest.raises(ValueError, match="changed"):
        MODULE.verify_hash("candidate", {"question": "changed"}, "0" * 64)


def test_final_report_has_no_publication_authority():
    report = MODULE.build_final_report(decisions(), {"manifest": "0" * 64})
    assert report["status"] == "proposal_only"
    assert report["published"] is False
    assert report["publication"] == {
        "authorized": False,
        "database_mutated": False,
    }


def test_only_new_and_clear_novelty_is_accepted():
    row = {
        "ready_for_final_selection": True,
        "error_type": None,
        "reviews": [{"novelty": "new", "clarity": "clear"}],
    }
    assert MODULE._accepted_novelty(row) is True
    assert MODULE._accepted_novelty(
        {**row, "reviews": [{"novelty": "uncertain", "clarity": "clear"}]}
    ) is False
    assert MODULE._accepted_novelty({**row, "error_type": "ValueError"}) is False
