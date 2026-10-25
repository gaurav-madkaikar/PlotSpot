import asyncio
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from movie_companion.evidence_store import SourceDocument


@pytest.fixture
def runner(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_movie_rag.py"
    spec = importlib.util.spec_from_file_location("movie_rag_runner_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCAL", tmp_path / "local")
    monkeypatch.setattr(module, "DATASET", tmp_path / "cases.json")
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Invalid setup must fail before any HTTP client")
    monkeypatch.setattr(module.httpx, "AsyncClient", forbidden_network)
    return module


def test_preparation_preserves_existing_learner_labels(runner):
    runner.DATASET.write_text('Learner work: do not overwrite')
    with pytest.raises(ValueError, match="will not overwrite"):
        asyncio.run(runner.prepare_source())
    assert runner.DATASET.read_text() == 'Learner work: do not overwrite'


@pytest.mark.parametrize("invalid", ["snapshot", "unknown_id"])
def test_bad_labels_fail_before_model_requests(runner, invalid, tmp_path):
    source = SourceDocument("enwiki-1", 157336, "Authored test source.", "Fixture", "https://en.wikipedia.org/w/index.php?oldid=1", "fixture-v1")
    key, passages = runner.catalogue(source)
    runner.LOCAL.mkdir()
    (runner.LOCAL / "source.json").write_text(json.dumps(asdict(source)))
    runner.DATASET.write_text(json.dumps({
        "version": "v1", "split": "development",
        "source_snapshot": "0" * 64 if invalid == "snapshot" else key,
        "cases": [{"id": "test", "question": "A question", "expected_status": "answered",
                   "relevant_passage_ids": ["foreign" if invalid == "unknown_id" else passages[0]["passage_id"]],
                   "required_phrase_groups": [["fixture"]]}],
    }))
    with pytest.raises(ValueError, match="snapshot changed|Unknown supporting"):
        asyncio.run(runner.evaluate(tmp_path / "report.json"))
    assert not (tmp_path / "report.json").exists()


def test_output_cannot_overwrite_labels(runner):
    runner.DATASET.write_text("Preserved labels")
    with pytest.raises(ValueError, match="must not overwrite"):
        asyncio.run(runner.evaluate(runner.DATASET))
    assert runner.DATASET.read_text() == "Preserved labels"
