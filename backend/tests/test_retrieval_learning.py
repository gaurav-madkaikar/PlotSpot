import pytest

import movie_companion.retrieval_learning as retrieval
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit, retrieve_passages


MODEL = "test-embedding-model"


def passage(passage_id, vector, *, movie_id=101, spoiler_status="safe", model=MODEL):
    return EmbeddedPassage(
        passage_id, movie_id, f"Synthetic passage {passage_id}", vector,
        model, "Authored learning fixture", spoiler_status,
    )


def retrieve(passages, **kwargs):
    return retrieve_passages([1.0, 0.0], passages, query_model=MODEL, movie_id=101, **kwargs)


def test_ranks_by_similarity_and_keeps_evidence_identity():
    a, b, c = passage("a", [0.0, 1.0]), passage("b", [1.0, 0.0]), passage("c", [1.0, 1.0])
    hits = retrieve([a, b, c], k=2)
    assert [hit.passage.passage_id for hit in hits] == ["b", "c"]
    assert hits[0].passage is b
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(2 ** -0.5)


def test_ties_use_passage_id_for_repeatable_results():
    hits = retrieve([passage("b", [1.0, 0.0]), passage("a", [1.0, 0.0])], k=2)
    assert [hit.passage.passage_id for hit in hits] == ["a", "b"]


def test_fewer_than_k_returns_available_evidence():
    assert len(retrieve([passage("a", [1.0, 0.0])], k=3)) == 1


def test_negative_score_is_not_disguised_as_probability():
    assert retrieve([passage("a", [-1.0, 0.0])], k=1)[0].score == pytest.approx(-1.0)


def test_ranking_does_not_reorder_original_inputs():
    inputs = [passage("a", [0.0, 1.0]), passage("b", [1.0, 0.0])]
    retrieval.rank_passages([1.0, 0.0], inputs, k=1)
    assert [item.passage_id for item in inputs] == ["a", "b"]


def test_scope_filters_run_before_learner_ranking(monkeypatch):
    safe = passage("safe", [0.0, 1.0])
    excluded = [
        passage("another-film", [1.0, 0.0], movie_id=202),
        passage("ending", [1.0, 0.0], spoiler_status="spoiler"),
        passage("unclassified", [1.0, 0.0], spoiler_status="unknown"),
    ]
    def inspect_scope(query, candidates, *, k):
        assert candidates == [safe]
        return [RetrievalHit(safe, 0.0)]
    monkeypatch.setattr(retrieval, "rank_passages", inspect_scope)
    assert retrieve([safe, *excluded])[0].passage is safe


def test_explicit_spoiler_permission_changes_eligible_evidence(monkeypatch):
    ending = passage("ending", [1.0, 0.0], spoiler_status="spoiler")
    def inspect_scope(query, candidates, *, k):
        assert candidates == [ending]
        return [RetrievalHit(ending, 1.0)]
    monkeypatch.setattr(retrieval, "rank_passages", inspect_scope)
    assert retrieve([ending], allow_spoilers=True)[0].passage is ending


def test_no_eligible_evidence_returns_empty_without_ranking(monkeypatch):
    def must_not_rank(*args, **kwargs):
        pytest.fail("No eligible evidence should bypass ranking")
    monkeypatch.setattr(retrieval, "rank_passages", must_not_rank)
    assert retrieve([]) == []
    assert retrieve([passage("other", [1.0, 0.0], movie_id=202)]) == []


@pytest.mark.parametrize("k", [0, 7, True])
def test_invalid_k_rejected(k):
    with pytest.raises(ValueError):
        retrieve([], k=k)


@pytest.mark.parametrize("candidate", [
    passage("a", [1.0]),
    passage("a", [0.0, 0.0]),
    passage("a", [float("nan"), 1.0]),
    passage("a", [1.0, 0.0], model="different-model"),
])
def test_incompatible_evidence_rejected(candidate):
    with pytest.raises(ValueError):
        retrieve([candidate])


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        retrieve([passage("a", [1.0, 0.0]), passage("a", [0.0, 1.0])])
