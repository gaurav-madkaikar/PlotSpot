import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from movie_companion.local_models import DIGESTS
from movie_companion.quiz_replacement_workflow import ReplacementDraft, ReplacementDrafts


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/prepare_quiz_replacement_completion.py"
)
SPEC = importlib.util.spec_from_file_location("quiz_replacement_completion_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_identity(*, planned):
    return {
        "policy": MODULE.POLICY,
        "pipeline_revision": MODULE.PIPELINE_REVISION,
        "manifest_sha256": "2" * 64,
        "contracts_sha256": "1" * 64,
        "source_review_sha256": "3" * 64,
        "evidence_review_sha256": "4" * 64,
        "recovered_evidence_review_sha256": "5" * 64,
        "model": "qwen3.5:9b",
        "model_digest": DIGESTS["qwen3.5:9b"],
        "planned": planned,
    }


def completion_target(question_id):
    return {
        "movie_id": 1,
        "title": "Film",
        "question_id": question_id,
        "old_question": "What old fact was tested?",
        "replacement_brief": "Test why the choice protects the family.",
        "remaining_questions": [],
        "evidence": {
            "citations": [
                {
                    "source_label": "Source",
                    "source_ref": "https://example.com/story",
                    "revision": "r1",
                    "excerpt": "The choice protects the family.",
                }
            ]
        },
        "intent": {
            "question_id": question_id,
            "focus": "the choice",
            "relation": "motivation",
            "required_concepts": [["protects"], ["family"]],
            "forbidden_details": [],
            "expected_answer_shape": "reason",
            "difficulty": "general_viewer",
        },
    }


def span(identifier):
    return {
        "span_id": identifier,
        "citation_index": 0,
        "text": "protects the family",
        "score": 10.0,
    }


def one_valid_replacement_draft(target_id):
    return ReplacementDrafts(
        items=[
            ReplacementDraft(
                target_id=target_id,
                question="Why does the character make the choice?",
                options=[
                    "protects the family",
                    "wins a prize",
                    "finds a map",
                    "changes a name",
                ],
                correct_index=0,
                evidence_quote="The choice protects the family.",
            )
        ]
    )


async def one_accepted_review(client, *, targets, drafts):
    return [
        {
            "target_id": "T1",
            "candidate": drafts.items[0].model_dump(),
            "deterministic_problems": [],
            "critic": {"decision": "accept"},
            "ready_for_assistant_review": True,
        }
    ]


def withheld_row(question_id):
    return {
        "movie_id": 1,
        "title": "Film",
        "question_id": question_id,
        "candidate": None,
        "withheld_reason": "writer_abstained",
        "ready_for_assistant_review": False,
        "error_type": None,
    }


def test_completion_runner_rejects_stale_checkpoint(tmp_path):
    output = tmp_path / "checkpoint.json"
    identity = valid_identity(planned=30)
    output.write_text(
        json.dumps(
            {
                **identity,
                "manifest_sha256": "0" * 64,
                "status": "running",
                "items": [],
                "published": False,
            }
        )
    )

    with pytest.raises(ValueError, match="checkpoint identity"):
        MODULE.resume_rows(output, identity)


def test_target_failure_does_not_drop_successful_sibling(monkeypatch):
    async def fake_generate(client, targets):
        return one_valid_replacement_draft("T1"), {
            "T1": {"answer_spans": [span("S1")], "writer_problems": []},
            "T2": {
                "answer_spans": [span("S1")],
                "writer_problems": ["intent_contract_not_satisfied"],
            },
        }

    monkeypatch.setattr(MODULE, "generate_locked_drafts", fake_generate)
    monkeypatch.setattr(MODULE, "review_drafts", one_accepted_review)
    rows = asyncio.run(
        MODULE.run_batch(
            None, [completion_target("q1"), completion_target("q2")]
        )
    )
    report = MODULE.build_report(valid_identity(planned=2), rows)

    assert {item["question_id"] for item in report["items"]} == {"q1", "q2"}
    assert report["items"][1]["withheld_reason"] == "intent_contract_not_satisfied"
    assert report["summary"]["writer_drafts"] == 1


def test_batch_failure_retries_targets_individually(monkeypatch):
    calls = []

    async def fake_generate(client, targets):
        calls.append(len(targets))
        if len(targets) > 1:
            raise ValueError("bad batch")
        return one_valid_replacement_draft("T1"), {
            "T1": {"answer_spans": [span("S1")], "writer_problems": []}
        }

    monkeypatch.setattr(MODULE, "generate_locked_drafts", fake_generate)
    monkeypatch.setattr(MODULE, "review_drafts", one_accepted_review)
    rows = asyncio.run(
        MODULE.run_batch(
            None, [completion_target("q1"), completion_target("q2")]
        )
    )

    assert calls == [2, 1, 1]
    assert len(rows) == 2 and all(row["candidate"] for row in rows)


def test_intent_failure_gets_one_auditable_repair(monkeypatch):
    calls = []

    async def fake_generate(client, targets, **kwargs):
        calls.append(kwargs.get("repair_feedback"))
        if kwargs.get("repair_feedback") is None:
            return ReplacementDrafts(items=[]), {
                "T1": {
                    "answer_spans": [span("S1")],
                    "writer_problems": ["missing_required_concept"],
                    "rejected_candidate": {
                        "question": "What happens next?",
                        "answer_span_id": "S1",
                        "answer": "protects the family",
                        "distractors": ["a", "b", "c"],
                    },
                }
            }
        return one_valid_replacement_draft("T1"), {
            "T1": {
                "answer_spans": [span("S1")],
                "writer_problems": [],
                "rejected_candidate": None,
            }
        }

    monkeypatch.setattr(MODULE, "generate_locked_drafts", fake_generate)
    monkeypatch.setattr(MODULE, "review_drafts", one_accepted_review)
    rows = asyncio.run(MODULE.run_batch(None, [completion_target("q1")]))

    assert len(calls) == 2 and calls[1]["T1"]["problems"] == [
        "missing_required_concept"
    ]
    assert rows[0]["candidate"] is not None
    assert [attempt["attempt"] for attempt in rows[0]["writer_attempts"]] == [
        "initial",
        "repair",
    ]


def test_completion_report_has_no_publication_authority():
    report = MODULE.build_report(valid_identity(planned=1), [withheld_row("q1")])

    assert report["status"] == "proposal_only"
    assert report["published"] is False
    assert report["publication"] == {
        "authorized": False,
        "database_mutated": False,
    }


def test_rejected_evidence_can_remain_in_audit_but_is_not_promoted():
    payload = {
        "policy": "assistant-replacement-evidence-editorial-v1",
        "status": "proposal_only",
        "published": False,
        "items": [
            {
                "movie_id": 1,
                "question_id": "q1",
                "editorial_decision": "reject",
                "selected_evidence": [{"excerpt": "Auditable but not approved."}],
            }
        ],
    }

    rows = MODULE._reviewed_evidence(
        payload,
        policy="assistant-replacement-evidence-editorial-v1",
        name="original evidence review",
    )

    assert rows[(1, "q1")]["editorial_decision"] == "reject"
