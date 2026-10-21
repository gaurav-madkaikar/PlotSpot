import json

import pytest

from movie_companion.orchestration_benchmark import (
    BenchmarkDataset, CASCADE_POLICY, comparison, project_relative_path,
)


def dataset():
    return {
        "policy": "plotspot-orchestration-holdout-v1",
        "created_at": "2026-10-16T00:00:00+00:00",
        "split": "holdout",
        "label_origin": "Frozen before either compared discussion pipeline was run.",
        "embedding_model": "nomic-embed-text:v1.5",
        "chat_model": "llama3.2:3b",
        "chunk_settings": {"max_chars": 600, "overlap_chars": 100},
        "sources": [{"movie_id": 1, "path": ".cache/expanded20/sources/1.json",
                     "sha256": "a" * 64, "revision": "revision", "snapshot": "b" * 64}],
        "cases": [{"id": "answer", "movie_id": 1, "title": "Film", "question": "Where?",
                   "expected_status": "answered", "reference_answer": "Here",
                   "reference_excerpt": "The answer is Here in this sufficiently long source sentence.",
                   "relevant_passage_ids": ["b" * 32 + "_001"],
                   "required_phrase_groups": [["Here"]]}],
    }


def sample(passed, duration, *, chat_calls):
    return {"grade": {"automated_pass": passed, "supporting_hit_at_3": True},
            "duration_seconds": duration, "error": None,
            "calls": [{"endpoint": "/api/chat", "model": "llama3.2:3b",
                       "prompt_tokens": 10, "output_tokens": 2, "total_duration_ns": 1_000_000_000}
                      for _ in range(chat_calls)] +
                     [{"endpoint": "/api/embed", "model": "nomic-embed-text:v1.5",
                       "prompt_tokens": None, "output_tokens": None, "total_duration_ns": 100_000_000}]}


def test_dataset_requires_answer_labels_and_current_model_policy():
    assert BenchmarkDataset.model_validate(dataset()).cases[0].reference_answer == "Here"
    broken = dataset(); broken["cases"][0]["reference_excerpt"] = None
    with pytest.raises(ValueError): BenchmarkDataset.model_validate(broken)


def test_dataset_accepts_separate_frozen_cascade_policy():
    data = dataset()
    data["policy"] = CASCADE_POLICY
    assert BenchmarkDataset.model_validate(data).policy == CASCADE_POLICY


def test_project_relative_path_normalizes_parent_segments(tmp_path):
    root = tmp_path / "project"
    nested = root / "evals"
    nested.mkdir(parents=True)
    target = nested / "data.json"
    target.write_text("{}")
    path_with_parent = root / "backend" / ".." / "evals" / "data.json"
    assert project_relative_path(path_with_parent, root=root) == "evals/data.json"
    broken = dataset(); broken["chat_model"] = "another-model"
    with pytest.raises(ValueError): BenchmarkDataset.model_validate(broken)


def test_comparison_reports_quality_latency_and_call_tradeoff():
    rows = [{"expected_status": "answered", "direct": sample(False, 1, chat_calls=1),
             "specialist": sample(True, 2, chat_calls=2)}]
    result = comparison(rows)
    assert result["specialist_pass_rate_delta_points"] == 100
    assert result["specialist_median_latency_ratio"] == 2
    assert result["direct"]["chat_calls"] == 1
    assert result["specialist"]["chat_calls"] == 2
    assert "improved" in result["conclusion"]
