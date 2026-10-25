from dataclasses import asdict, replace
import json
import subprocess
import sys

import pytest

from movie_companion.chunking_learning import chunk_text
from movie_companion.evidence_store import EvidenceStore, SourceDocument, snapshot_key


SOURCE = SourceDocument("orbit-production", 900000001, "Recorded washing-machine hum was slowed. Recycled fabric suits were silver.", "Authored fictional notes", "fixture://orbit-production", "v1", "safe")
SETTINGS = {"model": "test-embedding-v1", "max_chars": 40, "overlap_chars": 5}


def save(store, source=SOURCE):
    chunks = chunk_text(source.text, max_chars=40, overlap_chars=5)
    store.save_snapshot(source, chunks, [[1.0, 0.5] for _ in chunks], **SETTINGS)


def test_snapshot_reopens_and_preserves_provenance(tmp_path):
    store = EvidenceStore(tmp_path)
    assert not store.contains_snapshot(SOURCE, **SETTINGS)
    save(store)
    reopened = EvidenceStore(tmp_path)
    assert reopened.contains_snapshot(SOURCE, **SETTINGS)
    passages = reopened.load_snapshot(SOURCE, **SETTINGS)
    assert passages[0].text == SOURCE.text[:40]
    assert passages[0].movie_id == SOURCE.movie_id
    assert passages[0].spoiler_status == "safe"
    assert passages[0].vector == pytest.approx([1, 0.5])
    assert passages[0].location.text == SOURCE.text
    assert passages[0].location.start == 0
    assert passages[0].location.end == 40
    key = snapshot_key(SOURCE, **SETTINGS)
    assert passages[0].location.source_key == key
    stored = store._collection(SETTINGS["model"]).get(where={"snapshot": key})
    assert stored["metadatas"][0]["source_ref"] == SOURCE.source_ref
    assert stored["metadatas"][0]["revision"] == SOURCE.revision


@pytest.mark.parametrize("changed", [
    replace(SOURCE, text=SOURCE.text + " Extra."), replace(SOURCE, revision="v2"),
    replace(SOURCE, movie_id=202), replace(SOURCE, spoiler_status="unknown"),
])
def test_source_changes_invalidate_cache(tmp_path, changed):
    store = EvidenceStore(tmp_path)
    save(store)
    assert not store.contains_snapshot(changed, **SETTINGS)


@pytest.mark.parametrize("settings", [
    {**SETTINGS, "model": "other-model"}, {**SETTINGS, "max_chars": 45},
    {**SETTINGS, "overlap_chars": 6},
])
def test_model_or_policy_changes_invalidate_cache(tmp_path, settings):
    store = EvidenceStore(tmp_path)
    save(store)
    assert not store.contains_snapshot(SOURCE, **settings)


def test_incomplete_snapshot_is_not_a_cache_hit(tmp_path):
    store = EvidenceStore(tmp_path)
    save(store)
    passages = store.load_snapshot(SOURCE, **SETTINGS)
    store._collection(SETTINGS["model"]).delete(ids=[passages[0].passage_id])
    assert not store.contains_snapshot(SOURCE, **SETTINGS)
    with pytest.raises(ValueError):
        store.load_snapshot(SOURCE, **SETTINGS)
    save(store)
    assert store.contains_snapshot(SOURCE, **SETTINGS)


@pytest.mark.parametrize("vector", [[0.0, 0.0], [float("nan"), 1.0], [True, 1.0]])
def test_bad_vectors_rejected_before_write(tmp_path, vector):
    store = EvidenceStore(tmp_path)
    chunks = chunk_text(SOURCE.text, max_chars=40, overlap_chars=5)
    with pytest.raises(ValueError):
        store.save_snapshot(SOURCE, chunks, [vector for _ in chunks], **SETTINGS)
    assert not store.contains_snapshot(SOURCE, **SETTINGS)


def test_revision_load_never_mixes_historical_chunks(tmp_path):
    store = EvidenceStore(tmp_path)
    save(store)
    new = replace(SOURCE, revision="v2", text="The revised fixture has a new sound technique.")
    save(store, new)
    assert store.contains_snapshot(SOURCE, **SETTINGS)
    assert store.contains_snapshot(new, **SETTINGS)
    assert store.load_snapshot(new, **SETTINGS)[0].text == new.text[:40]


def test_unknown_spoilers_preserved(tmp_path):
    unknown = replace(SOURCE, spoiler_status="unknown")
    store = EvidenceStore(tmp_path)
    save(store, unknown)
    assert store.load_snapshot(unknown, **SETTINGS)[0].spoiler_status == "unknown"


def test_model_dimensions_separated_between_collections(tmp_path):
    store = EvidenceStore(tmp_path)
    save(store)
    chunks = chunk_text(SOURCE.text, max_chars=40, overlap_chars=5)
    settings = {**SETTINGS, "model": "three-dim-model"}
    store.save_snapshot(SOURCE, chunks, [[1.0, 0.5, 0.2] for _ in chunks], **settings)
    assert len(store.load_snapshot(SOURCE, **settings)[0].vector) == 3


def test_persists_into_a_separate_python_process(tmp_path):
    save(EvidenceStore(tmp_path))
    code = """
import json, sys
from pathlib import Path
from movie_companion.evidence_store import EvidenceStore, SourceDocument
source = SourceDocument(**json.loads(sys.argv[2]))
store = EvidenceStore(Path(sys.argv[1]))
settings = json.loads(sys.argv[3])
assert store.contains_snapshot(source, **settings)
assert store.load_snapshot(source, **settings)[0].text == source.text[:40]
print('persistent snapshot reopened')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), json.dumps(asdict(SOURCE)), json.dumps(SETTINGS)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    assert "persistent snapshot reopened" in result.stdout


def test_source_chunk_count_is_bounded_before_storage():
    source = replace(SOURCE, text="X" * 201)
    with pytest.raises(ValueError, match="200 chunks"):
        snapshot_key(source, model="test", max_chars=1, overlap_chars=0)
