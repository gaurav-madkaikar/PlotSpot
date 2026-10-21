"""Prepare frozen public evidence, or evaluate the real local RAG pipeline."""

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import platform
import time

import httpx

from movie_companion.chunking_learning import chunk_text
from movie_companion.evidence_store import EvidenceStore, SourceDocument, snapshot_key
from movie_companion.grounding_learning import answer_from_hits, build_grounded_prompt
from movie_companion.ingestion_learning import ingest_source
from movie_companion.movie_qa_learning import answer_movie_question
from movie_companion.movie_rag_eval import MovieRagDataset, grade_case, validate_snapshot
from movie_companion.wikipedia_source import fetch_movie_source


ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "data/private/movie-rag"
DATASET = ROOT / "evals/movie-rag/cases.json"
EMBEDDING_MODEL = "nomic-embed-text:v1.5"
CHAT_MODEL = "llama3.2:3b"
CHUNK_SETTINGS = {"max_chars": 600, "overlap_chars": 100}


def catalogue(source):
    key = snapshot_key(source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
    return key, [{"passage_id": f"{key[:32]}_{index:03}", **asdict(chunk)}
                 for index, chunk in enumerate(chunk_text(source.text, **CHUNK_SETTINGS))]


async def prepare_source():
    # Protect learner labels and their frozen inputs before any network work.
    if DATASET.exists() or (LOCAL / "source.json").exists():
        raise ValueError("Frozen inputs or labels already exist; preparation will not overwrite them")
    async with httpx.AsyncClient(
        base_url="https://en.wikipedia.org", timeout=30, trust_env=False,
        follow_redirects=False,
        headers={"User-Agent": "MovieCompanionLearning/0.1 (local educational source reader)"},
    ) as client:
        source = await fetch_movie_source(client, movie_id=157336)
    key, passages = catalogue(source)
    # Worked label from the explicitly reviewed Music statement, not a model answer.
    music = [p["passage_id"] for p in passages if "returned to score Interstellar" in p["text"]]
    if not music:
        raise ValueError("Reviewed composer statement changed; label the new source manually")
    dataset = MovieRagDataset.model_validate({
        "version": "movie-rag-dev-v1", "split": "development", "source_snapshot": key,
        "cases": [
            {"id": "composer", "question": "Who composed the music for Interstellar?",
             "expected_status": "answered", "relevant_passage_ids": music,
             "required_phrase_groups": [["Hans Zimmer"]]},
            {"id": "missing-personal-evidence", "question": "What did I write in my private diary after watching Interstellar?",
             "expected_status": "insufficient_evidence", "relevant_passage_ids": [], "required_phrase_groups": []},
        ],
    })
    LOCAL.mkdir(parents=True, exist_ok=True)
    DATASET.parent.mkdir(parents=True, exist_ok=True)
    (LOCAL / "source.json").write_text(json.dumps(asdict(source), ensure_ascii=False, indent=2) + "\n")
    (LOCAL / "passages.json").write_text(json.dumps({"source_snapshot": key, "source_ref": source.source_ref, "passages": passages}, ensure_ascii=False, indent=2) + "\n")
    DATASET.write_text(dataset.model_dump_json(indent=2) + "\n")
    print(f"Frozen revision: {source.revision}\nPassages: {len(passages)}\nCatalogue: {LOCAL / 'passages.json'}\nLabels: {DATASET}")


async def evaluate(output):
    if output.resolve() in {DATASET.resolve(), (LOCAL / "source.json").resolve(), (LOCAL / "passages.json").resolve()}:
        raise ValueError("Report output must not overwrite frozen inputs or labels")
    source_path = LOCAL / "source.json"
    if not source_path.exists() or not DATASET.exists():
        raise ValueError("Prepare frozen source and labels first with --prepare-source")
    if source_path.stat().st_size > 1_000_000 or DATASET.stat().st_size > 200_000:
        raise ValueError("Evaluation input file exceeds size limit")
    source = SourceDocument(**json.loads(source_path.read_text()))
    if source.movie_id != 157336 or not source.source_id.startswith("enwiki-"):
        raise ValueError("Evaluation accepts only the reviewed Interstellar source")
    key, passages = catalogue(source)
    dataset_bytes = DATASET.read_bytes()
    dataset = MovieRagDataset.model_validate_json(dataset_bytes)
    validate_snapshot(dataset, key, {p["passage_id"] for p in passages})
    rows = []
    async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=120, trust_env=False, follow_redirects=False) as client:
        # Read installed identities where available, without changing models/settings.
        digests = {}
        try:
            tags = await client.get("/api/tags")
            tags.raise_for_status()
            digests = {record["name"]: record.get("digest") for record in tags.json().get("models", [])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
        store = await asyncio.to_thread(EvidenceStore, ROOT / "data/chroma/eval")
        async with asyncio.timeout(180):
            ingestion = await ingest_source(client, store=store, source=source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
        embedded = await asyncio.to_thread(store.load_snapshot, source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
        for case in dataset.cases:
            hits, answer, error = [], None, None
            start = time.perf_counter()
            try:
                async with asyncio.timeout(180):
                    answer = await answer_movie_question(
                        client, question=case.question, passages=embedded, movie_id=source.movie_id,
                        allow_spoilers=True, embedding_model=EMBEDDING_MODEL,
                        chat_model=CHAT_MODEL, on_retrieved=hits.extend,
                    )
            except (httpx.HTTPError, ValueError, TimeoutError) as exc:
                error = type(exc).__name__
                error_detail = str(exc)[:400]
            row = {
                "id": case.id, "question": case.question,
                "expected_status": case.expected_status,
                "labelled_supporting_ids": case.relevant_passage_ids,
                "retrieved": [{"passage_id": hit.passage.passage_id, "score": hit.score} for hit in hits],
                "answer": asdict(answer) if answer else None, "error": error,
                "error_detail": error_detail if error else None,
                "duration_seconds": round(time.perf_counter() - start, 3),
                **grade_case(case, hits, answer),
            }
            rows.append(row)
            print(f"{'PASS' if row['automated_pass'] else 'FAIL'} {case.id}: hit@3={row['supporting_hit_at_3']}, {row['duration_seconds']}s", flush=True)
    labelled = [row for row in rows if row["supporting_hit_at_3"] is not None]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset.version, "split": dataset.split,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "source_snapshot": key, "source_revision": source.revision, "source_ref": source.source_ref,
        "prompt_source_sha256": hashlib.sha256(inspect.getsource(build_grounded_prompt).encode()).hexdigest(),
        "grounding_boundary_sha256": hashlib.sha256(inspect.getsource(answer_from_hits).encode()).hexdigest(),
        "pipeline_source_sha256": hashlib.sha256(inspect.getsource(answer_movie_question).encode()).hexdigest(),
        "models": {name: digests.get(name) for name in (EMBEDDING_MODEL, CHAT_MODEL)},
        "runtime": {"platform": platform.platform(), "python": platform.python_version()},
        "ingestion": ingestion, "chunk_settings": CHUNK_SETTINGS,
        "generation_settings": "Schema-constrained JSON; temperature=0; seed=7; stream=false; sequential; no retries",
        "token_usage": None,
        "summary": {"automated_passed": sum(row["automated_pass"] for row in rows), "total": len(rows),
                    "supporting_hits": sum(row["supporting_hit_at_3"] for row in labelled),
                    "retrieval_labelled_cases": len(labelled),
                    "supporting_hit_rate_at_3": sum(row["supporting_hit_at_3"] for row in labelled) / len(labelled) if labelled else None,
                    "generation_errors": sum(row["error"] is not None for row in rows)},
        "limitations": ["Small development set, not held out or a security benchmark.",
                        "Recall refers only to annotated IDs, not all potentially relevant corpus passages.",
                        "Phrase/citation checks are smoke checks; human claim-support review pending.",
                        "Document model digest is not part of the persistent cache key; temperature/seed do not guarantee identical outputs across runtimes.",
                        "The labelled missing-evidence case has no positive retrieval metric."],
        "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {output}")
    return 0 if all(row["automated_pass"] for row in rows) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-source", action="store_true", help="Freeze public whole-article evidence; may include spoilers; no model inference")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/movie-rag/baseline.json")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(prepare_source() if args.prepare_source else evaluate(args.output)))
    except (ValueError, OSError, httpx.HTTPError, TimeoutError) as exc:
        parser.exit(2, f"Evaluation setup failed ({type(exc).__name__}): {exc}\n")
