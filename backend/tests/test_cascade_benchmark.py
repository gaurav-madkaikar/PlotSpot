import pytest

from movie_companion.cascade_benchmark import compare_cascade, compose_cascade, fallback_reason


def sample(*, passed=True, status="answered", answer="A complete answer.", error=None, chats=1):
    value = None if status == "invalid" else {"status": status, "answer": answer, "citation_ids": []}
    return {"answer": value, "error": error, "duration_seconds": 2,
            "grade": {"automated_pass": passed, "supporting_hit_at_3": passed},
            "calls": [{"endpoint": "/api/chat", "model": "local", "prompt_tokens": 10,
                       "output_tokens": 2, "total_duration_ns": 1_000_000_000} for _ in range(chats)]}


@pytest.mark.parametrize(("question", "direct", "reason"), [
    ("Where?", sample(error="ValueError"), "direct_generation_or_validation_error"),
    ("Where?", sample(status="invalid"), "direct_invalid_response"),
    ("Where?", sample(status="insufficient_evidence"), "direct_insufficient_evidence"),
    ("How many years?", sample(answer="Three"), "requested_time_unit_missing_from_answer"),
    ("Where does he go?", sample(answer="He goes to another country."), "generic_location_answer"),
    ("How many ships?", sample(answer="Twelve"), None),
])
def test_preregistered_fallback_triggers(question, direct, reason):
    assert fallback_reason(question, direct) == reason


def test_cascade_adds_cost_only_when_fallback_runs():
    rows = [
        {"id": "a", "question": "Where?", "expected_status": "answered",
         "direct": sample(passed=True), "specialist": sample(passed=True, chats=2)},
        {"id": "b", "question": "Where?", "expected_status": "insufficient_evidence",
         "direct": sample(passed=True, status="insufficient_evidence"),
         "specialist": sample(passed=True, status="insufficient_evidence", chats=2)},
    ]
    composed = compose_cascade(rows)
    assert composed[0]["cascade"]["selected_arm"] == "direct"
    assert len(composed[0]["cascade"]["calls"]) == 1
    assert composed[1]["cascade"]["selected_arm"] == "specialist"
    assert len(composed[1]["cascade"]["calls"]) == 3
    comparison = compare_cascade(rows)
    assert comparison["fallbacks"]["count"] == 1
    assert comparison["cascade"]["chat_calls"] == 4
