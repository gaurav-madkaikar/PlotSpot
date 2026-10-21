import json
from pathlib import Path

from movie_companion.grounding_eval import check_answer
from movie_companion.grounding_learning import GroundedAnswer


DATASET = json.loads((Path(__file__).resolve().parents[2] / "evals/grounding/cases.json").read_text())
SOUND = DATASET["cases"][0]


def test_dataset_is_small_explicit_development_split():
    assert DATASET["split"] == "development"
    assert len(DATASET["cases"]) == 6
    assert len({case["id"] for case in DATASET["cases"]}) == 6
    for case in DATASET["cases"]:
        ids = {record["passage_id"] for record in case["evidence"]}
        assert set(case["expected_citation_ids"]) <= ids


def test_supported_answer_passes_smoke_checks():
    answer = GroundedAnswer("answered", "They slowed a washing-machine hum.", ("sound",))
    assert check_answer(SOUND, answer) == []


def test_missing_expected_content_detected():
    failures = check_answer(SOUND, GroundedAnswer("answered", "They used a keyboard.", ("sound",)))
    assert len(failures) == 2


def test_wrong_status_and_ids_detected():
    failures = check_answer(SOUND, GroundedAnswer("insufficient_evidence", "Missing", ()))
    assert any("status" in failure for failure in failures)
    assert any("Citations" in failure for failure in failures)


def test_injection_marker_detected_case_insensitively():
    case = DATASET["cases"][4]
    failures = check_answer(case, GroundedAnswer("answered", "They slowed a washing machine. injection_accepted", ("sound",)))
    assert any("Forbidden" in failure for failure in failures)


def test_keywords_do_not_establish_claim_support():
    answer = GroundedAnswer("answered", "They slowed a washing machine. The film earned a billion dollars.", ("sound",))
    assert check_answer(SOUND, answer) == []  # Human review must catch the extra unsupported claim.
