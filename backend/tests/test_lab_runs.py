from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

import pytest

from movie_companion.lab_runs import LabRunReader


def preparation_database(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "b" * 32,
        "movie_id": 157336,
        "state": "needs_review",
        "phase": "finished",
        "updated_at": "2026-10-24T10:00:00+00:00",
        "message": "raw private status",
        "question": "private question",
        "email": "user@example.com",
        "report": {
            "sources": [{"text": "evidence quote"}, {"prompt": "raw prompt"}],
            "batches": [{"evidence": [{"text": "hidden"}, {"text": "hidden"}]}],
            "degraded": False,
        },
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE jobs (movie_id INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, "
            "state TEXT NOT NULL, payload TEXT NOT NULL, sequence INTEGER NOT NULL, "
            "attempts INTEGER NOT NULL DEFAULT 0, owner TEXT, expires REAL, "
            "cancel_requested INTEGER NOT NULL DEFAULT 0)"
        )
        connection.execute(
            "INSERT INTO jobs (movie_id,id,state,payload,sequence) VALUES (?,?,?,?,?)",
            (157336, payload["id"], payload["state"], json.dumps(payload), 1),
        )


def story_trace(root: Path):
    root.mkdir(parents=True)
    path = root / ("603-" + "a" * 32 + ".json")
    path.write_text(
        json.dumps(
            {
                "movie_id": 603,
                "mode": "quiz",
                "source_cache": "cached",
                "wiki_revision": "wiki-v1",
                "script_revision": "script-v1",
                "index": {"chunks": 15},
                "wiki_hits": [{"text": "private question"}],
                "script_hits": [{"text": "evidence quote"}, {"prompt": "raw prompt"}],
                "initial_candidate_count": 2,
                "candidate_count": 1,
                "decisions": [{"reason": "model reasoning"}],
            }
        )
    )
    moment = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc).timestamp()
    os.utime(path, (moment, moment))
    return path


def test_reader_projects_runs_without_sensitive_content(tmp_path):
    db_path = tmp_path / "jobs.db"
    trace_root = tmp_path / "traces"
    preparation_database(db_path)
    story_trace(trace_root)
    titles = {603: "The Matrix", 157336: "Interstellar"}
    reader = LabRunReader(db_path, trace_root, titles.get)

    runs, warnings = reader.list(workflow=None, state=None, limit=10)

    assert [run.id.split("_")[0] for run in runs] == ["story", "prep"]
    assert [run.title for run in runs] == ["The Matrix", "Interstellar"]
    assert warnings == []
    encoded = json.dumps([run.model_dump(mode="json") for run in runs])
    for secret in [
        "private question",
        "evidence quote",
        "user@example.com",
        "raw prompt",
        "model reasoning",
        "raw private status",
    ]:
        assert secret not in encoded

    detail = reader.get(runs[0].id)
    assert detail is not None
    assert [stage.name for stage in detail.stages] == [
        "index",
        "retrieve",
        "generate",
        "verify",
    ]
    assert "script_hits" not in detail.model_dump_json()


def test_reader_filters_and_caps_results(tmp_path):
    db_path = tmp_path / "jobs.db"
    trace_root = tmp_path / "traces"
    preparation_database(db_path)
    story_trace(trace_root)
    reader = LabRunReader(db_path, trace_root)

    runs, _ = reader.list(workflow="preparation", state="needs_review", limit=1)

    assert len(runs) == 1
    assert runs[0].workflow == "preparation"
    with pytest.raises(ValueError, match="limit"):
        reader.list(None, None, 51)
    with pytest.raises(ValueError, match="workflow"):
        reader.list("unknown", None, 10)


def test_reader_reports_missing_and_invalid_sources_without_paths(tmp_path):
    reader = LabRunReader(tmp_path / "missing.db", tmp_path / "missing-traces")

    runs, warnings = reader.list(None, None, 10)

    assert runs == []
    assert {warning.code for warning in warnings} == {"missing_source"}
    assert str(tmp_path) not in json.dumps(
        [warning.model_dump() for warning in warnings]
    )


def test_reader_rejects_trace_symlink_and_oversized_trace(tmp_path):
    db_path = tmp_path / "missing.db"
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    outside = tmp_path / ("603-" + "c" * 32 + ".json")
    outside.write_text("{}")
    (trace_root / ("603-" + "b" * 32 + ".json")).symlink_to(outside)
    (trace_root / ("603-" + "d" * 32 + ".json")).write_text("x" * 1_000_001)

    runs, warnings = LabRunReader(db_path, trace_root).list(None, None, 10)

    assert runs == []
    assert any(warning.code == "invalid_source" for warning in warnings)


def test_get_validates_ids_and_returns_none_for_unknown(tmp_path):
    reader = LabRunReader(tmp_path / "missing.db", tmp_path / "missing-traces")

    with pytest.raises(ValueError, match="run ID"):
        reader.get("../../private")
    assert reader.get("story_" + "f" * 32) is None
