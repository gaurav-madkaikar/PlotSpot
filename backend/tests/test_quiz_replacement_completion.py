import json

import pytest

from movie_companion.quiz_replacement_completion import (
    CompletionManifest,
    NarrativeIntent,
    load_completion_manifest,
    load_intent_contracts,
)
from movie_companion.research_checkpoint import digest


HASH = "0" * 64


def target(lane, index):
    return {
        "movie_id": index + 1,
        "title": f"Film {index}",
        "question_id": f"q{index}",
        "old_question": "What granular fact was tested?",
        "old_answer": "A granular answer",
        "replacement_brief": "Replace it with a meaningful narrative question.",
        "bank_version": f"research-{index}",
        "bank_sha256": HASH,
        "lane": lane,
        "originating_artifacts": {"review": HASH},
    }


def manifest():
    rows = [target("intent", index) for index in range(13)]
    rows += [target("evidence", index) for index in range(13, 30)]
    rows += [target("novelty", 30)]
    return CompletionManifest(
        policy="quiz-replacement-completion-manifest-v1",
        source_review_sha256=HASH,
        evidence_review_sha256=HASH,
        whole_bank_review_sha256=HASH,
        items=rows,
    )


def contract(question_id):
    return {
        "question_id": question_id,
        "focus": "the choice to protect the family",
        "relation": "motivation",
        "required_concepts": [["protect", "save"], ["family"]],
        "forbidden_details": ["three years"],
        "expected_answer_shape": "reason",
        "difficulty": "general_viewer",
    }


def test_narrative_intent_accepts_reviewed_values_and_rejects_unknown_types():
    intent = NarrativeIntent.model_validate(contract("q1"))

    assert intent.expected_answer_shape == "reason"
    with pytest.raises(ValueError):
        NarrativeIntent(
            question_id="q1",
            focus="a technical detail",
            relation="technical_detail",
            required_concepts=[["detail"]],
            forbidden_details=[],
            expected_answer_shape="number",
            difficulty="general_viewer",
        )


def test_narrative_intent_rejects_empty_or_unbounded_alias_groups():
    with pytest.raises(ValueError, match="one to five"):
        NarrativeIntent.model_validate(
            {**contract("q1"), "required_concepts": [[]]}
        )
    with pytest.raises(ValueError, match="one to five"):
        NarrativeIntent.model_validate(
            {**contract("q1"), "required_concepts": [[str(i) for i in range(6)]]}
        )


def test_manifest_requires_exact_lane_counts_and_unique_target_identity():
    value = manifest()

    assert value.summary == {
        "unresolved": 31,
        "intent": 13,
        "evidence": 17,
        "novelty": 1,
    }
    with pytest.raises(ValueError, match="Duplicate"):
        CompletionManifest(
            policy=value.policy,
            source_review_sha256=HASH,
            evidence_review_sha256=HASH,
            whole_bank_review_sha256=HASH,
            items=[value.items[0], value.items[0], *value.items[2:]],
        )


def test_manifest_rejects_changed_lane_counts():
    value = manifest().model_dump()
    value["items"][0]["lane"] = "evidence"

    with pytest.raises(ValueError, match="lane counts"):
        CompletionManifest.model_validate(value)


def test_reviewed_contracts_cover_every_generative_target_exactly_once(tmp_path):
    value = manifest()
    expected = [item.question_id for item in value.items if item.lane != "novelty"]
    path = tmp_path / "contracts.json"
    path.write_text(
        json.dumps(
            {
                "policy": "quiz-replacement-intent-contracts-v1",
                "status": "reviewed",
                "manifest_sha256": digest(value.model_dump(mode="json")),
                "items": [contract(question_id) for question_id in expected],
            }
        )
    )

    contracts = load_intent_contracts(path, manifest=value)

    assert set(contracts) == set(expected)
    assert all(isinstance(item, NarrativeIntent) for item in contracts.values())


def test_contract_loader_rejects_missing_duplicate_or_unreviewed_scope(tmp_path):
    value = manifest()
    expected = [item.question_id for item in value.items if item.lane != "novelty"]
    for name, status, rows in (
        ("missing", "reviewed", expected[:-1]),
        ("duplicate", "reviewed", [expected[0], *expected]),
        ("unreviewed", "draft", expected),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "policy": "quiz-replacement-intent-contracts-v1",
                    "status": status,
                    "manifest_sha256": digest(value.model_dump(mode="json")),
                    "items": [contract(question_id) for question_id in rows],
                }
            )
        )
        with pytest.raises(ValueError):
            load_intent_contracts(path, manifest=value)


def test_completion_manifest_loader_checks_proposal_metadata_and_summary(tmp_path):
    value = manifest()
    path = tmp_path / "manifest.json"
    payload = {
        **value.model_dump(mode="json"),
        "summary": value.summary,
        "status": "proposal_only",
        "published": False,
        "publication": {"authorized": False, "database_mutated": False},
    }
    path.write_text(json.dumps(payload))

    assert load_completion_manifest(path) == value
    payload["summary"]["intent"] = 12
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="summary changed"):
        load_completion_manifest(path)
