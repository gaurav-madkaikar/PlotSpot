import copy
import json

import pytest

from movie_companion.generation_ablation import analyze_generation_exports


def export(movie_id=1):
    return {"movie_id": movie_id, "report_sha256": "a" * 64, "all_candidates": [
        {"id": "F1", "kind": "fact", "decision": "accept", "ready": True, "retained": True},
        {"id": "F2", "kind": "fact", "decision": "accept", "ready": True, "retained": False},
        {"id": "Q1", "kind": "question", "decision": "accept", "ready": False, "retained": False},
        {"id": "Q2", "kind": "question", "decision": "reject", "ready": False, "retained": False},
    ]}


def saved(tmp_path, payload):
    path = tmp_path / f"{payload['movie_id']}.json"
    path.write_text(json.dumps(payload))
    return path, json.loads(path.read_text())


def test_ablation_reports_each_stage_without_calling_it_accuracy(tmp_path):
    report = analyze_generation_exports([saved(tmp_path, export())])
    assert report["overall"]["writer_candidates"] == 4
    assert report["overall"]["critic_accepted"] == 3
    assert report["overall"]["specialist_ready"] == 2
    assert report["overall"]["reviewed_published"] == 1
    assert report["overall"]["full_pipeline_workload_reduction_percent"] == 50
    assert report["comparison"]["writer_plus_critic_and_readiness"]["known_published_items_present"] == 1
    assert "not semantic precision" in report["limitations"][1]


@pytest.mark.parametrize("change", ["duplicate_movie", "duplicate_candidate", "ready_reject", "published_not_ready"])
def test_invalid_or_leaky_funnel_states_are_rejected(tmp_path, change):
    first = export()
    exports = [saved(tmp_path, first)]
    if change == "duplicate_movie":
        second = export()
        path = tmp_path / "duplicate.json"; path.write_text(json.dumps(second))
        exports.append((path, json.loads(path.read_text())))
    elif change == "duplicate_candidate":
        first["all_candidates"][1]["id"] = "F1"; exports = [saved(tmp_path, first)]
    elif change == "ready_reject":
        first["all_candidates"][3]["ready"] = True; exports = [saved(tmp_path, first)]
    else:
        first["all_candidates"][2]["retained"] = True; exports = [saved(tmp_path, first)]
    with pytest.raises(ValueError):
        analyze_generation_exports(exports)
