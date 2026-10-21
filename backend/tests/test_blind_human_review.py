import copy

import pytest

from movie_companion.blind_human_review import build_blind_packet, score_blind_packet


def run_report():
    answer = {"status": "answered", "answer": "The place.", "citation_ids": ["p1"]}
    abstain = {"status": "insufficient_evidence", "answer": "Insufficient.", "citation_ids": []}
    return {"cases": [
        {"id": "answerable", "title": "Film", "question": "Where?", "expected_status": "answered",
         "direct": {"answer": answer, "retrieved_ids": ["p1", "p2"]},
         "specialist": {"answer": answer, "retrieved_ids": ["p1"]}},
        {"id": "missing", "title": "Film", "question": "Private?", "expected_status": "insufficient_evidence",
         "direct": {"answer": abstain, "retrieved_ids": []},
         "specialist": {"answer": None, "retrieved_ids": []}},
    ]}


def complete(packet):
    result = copy.deepcopy(packet)
    for item in result["items"]:
        if item["response_status"] == "answered":
            item["review"] = {"correctness": "correct", "citation_support": "fully_supported",
                              "completeness": "complete", "abstention": "not_applicable", "notes": ""}
        else:
            item["review"] = {"correctness": "incorrect", "citation_support": "not_applicable",
                              "completeness": "not_applicable", "abstention": "appropriate", "notes": ""}
    return result


def test_packet_is_deterministic_blinded_and_keeps_key_separate():
    packet, key = build_blind_packet(run_report(), passage_text={"p1": "Evidence one."}, seed=7)
    again, _ = build_blind_packet(run_report(), passage_text={"p1": "Evidence one."}, seed=7)
    assert packet == again and len(packet["items"]) == 4
    assert all("arm" not in item and "expected_status" not in item for item in packet["items"])
    assert {row["arm"] for row in key["mapping"]} == {"direct", "specialist"}
    assert any(item["response_status"] == "invalid_response" for item in packet["items"])


def test_completed_packet_decodes_and_scores_both_arms():
    packet, key = build_blind_packet(run_report(), passage_text={"p1": "Evidence one."}, seed=7)
    reviewed = complete(packet)
    result = score_blind_packet(reviewed, key)
    assert result["summary"]["direct"]["cases"] == 2
    assert result["summary"]["specialist"]["cases"] == 2


def test_incomplete_or_mismatched_review_is_rejected():
    packet, key = build_blind_packet(run_report(), passage_text={"p1": "Evidence one."}, seed=7)
    with pytest.raises(ValueError, match="incomplete"):
        score_blind_packet(packet, key)
    reviewed = complete(packet)
    key["packet_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="differs"):
        score_blind_packet(reviewed, key)
