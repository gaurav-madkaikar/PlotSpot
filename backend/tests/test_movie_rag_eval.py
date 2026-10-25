import pytest
from pydantic import ValidationError

from movie_companion.grounding_learning import GroundedAnswer
from movie_companion.movie_rag_eval import MovieRagCase, MovieRagDataset, grade_case, validate_snapshot
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit


def case(**changes):
    return MovieRagCase(**({"id": "composer", "question": "Who composed it?", "expected_status": "answered", "relevant_passage_ids": ["music"], "required_phrase_groups": [["Hans Zimmer"]]} | changes))


def hit(identifier):
    return RetrievalHit(EmbeddedPassage(identifier, 157336, "Authored fixture", [1.0], "model", "Fixture", "unknown"), 0.8)


def test_retrieval_and_answer_checks_are_separate():
    result = grade_case(case(), [hit("music")], GroundedAnswer("answered", "A composer.", ("music",)))
    assert result["supporting_hit_at_3"] is True
    assert result["automated_pass"] is False
    assert "Missing expected phrase" in result["failures"][0]


def test_retrieval_miss_is_not_hidden_by_correct_remembered_answer():
    result = grade_case(case(), [hit("other")], GroundedAnswer("answered", "Hans Zimmer.", ("other",)))
    assert result["supporting_hit_at_3"] is False
    assert result["automated_pass"] is False


def test_partial_annotated_recall_and_supported_answer():
    result = grade_case(case(relevant_passage_ids=["music", "credits"]), [hit("music")], GroundedAnswer("answered", "Hans Zimmer.", ("music",)))
    assert result["annotated_id_recall_at_3"] == 0.5
    assert result["automated_pass"] is True


def test_abstention_excluded_from_retrieval_denominator():
    missing = case(expected_status="insufficient_evidence", relevant_passage_ids=[], required_phrase_groups=[])
    result = grade_case(missing, [hit("other")], GroundedAnswer("insufficient_evidence", "No evidence.", ()))
    assert result["supporting_hit_at_3"] is None
    assert result["annotated_id_recall_at_3"] is None
    assert result["automated_pass"] is True


def test_foreign_citation_and_model_failure_are_recorded():
    assert "Citation outside retrieved evidence" in grade_case(case(), [hit("music")], GroundedAnswer("answered", "Hans Zimmer.", ("foreign",)))["failures"]
    assert "Generation or response validation failed" in grade_case(case(), [hit("music")], None)["failures"]


@pytest.mark.parametrize("changes", [{"question": " "}, {"relevant_passage_ids": []}, {"required_phrase_groups": [[]]}, {"relevant_passage_ids": ["music", "music"]}, {"expected_status": "insufficient_evidence"}, {"unexpected": True}])
def test_invalid_labels_rejected(changes):
    with pytest.raises(ValidationError):
        case(**changes)


def test_fingerprint_unknown_ids_and_duplicate_cases_rejected():
    data = MovieRagDataset(version="v1", split="development", source_snapshot="a" * 64, cases=[case()])
    validate_snapshot(data, "a" * 64, {"music"})
    with pytest.raises(ValueError, match="snapshot changed"):
        validate_snapshot(data, "b" * 64, {"music"})
    with pytest.raises(ValueError, match="Unknown supporting"):
        validate_snapshot(data, "a" * 64, {"other"})
    with pytest.raises(ValidationError):
        MovieRagDataset(version="v1", split="development", source_snapshot="a" * 64, cases=[case(), case()])
