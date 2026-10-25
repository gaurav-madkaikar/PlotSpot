"""Compare direct single-agent RAG with PlotSpot's specialist answer pipeline."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
from time import perf_counter

import httpx

from movie_companion import discussion_context, discussion_retrieval, discussion_support, grounding_learning
from movie_companion.discussion_retrieval import retrieve_discussion_passages
from movie_companion.embedding_learning import embed_texts
from movie_companion.evidence_store import EvidenceStore
from movie_companion.grounding_learning import answer_from_hits
from movie_companion.ingestion_learning import ingest_source
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.movie_qa_learning import answer_movie_question
from movie_companion.movie_questions import MovieQuestionService
from movie_companion.movie_rag_eval import MovieRagCase, grade_case
from movie_companion.orchestration_benchmark import (
    load_frozen_dataset, comparison, project_relative_path, render_comparison,
)


ROOT = Path(__file__).resolve().parents[2]


class CallMeter:
    def __init__(self):
        self.active = None
        self.records = []

    async def request(self, request):
        request.extensions["benchmark_arm"] = self.active

    async def response(self, response):
        arm = response.request.extensions.get("benchmark_arm")
        if arm is None or response.request.url.path not in ("/api/chat", "/api/embed"):
            return
        await response.aread()
        request = json.loads(response.request.content)
        body = response.json() if response.status_code < 400 else {}
        self.records.append({
            "arm": arm,
            "endpoint": response.request.url.path,
            "model": request.get("model"),
            "status_code": response.status_code,
            "prompt_tokens": body.get("prompt_eval_count"),
            "output_tokens": body.get("eval_count"),
            "total_duration_ns": body.get("total_duration"),
        })

    async def measure(self, arm, operation):
        start = len(self.records); self.active = arm; began = perf_counter()
        try:
            value = await operation()
            error = None
        except (ValueError, httpx.HTTPError, TimeoutError) as exc:
            value = None; error = type(exc).__name__
        finally:
            duration = round(perf_counter() - began, 3)
            self.active = None
        return value, error, duration, self.records[start:]


async def direct_answer(client, *, case, passages, dataset):
    traces = []
    vector = (await embed_texts(client=client, model=dataset.embedding_model,
                                texts=[f"search_query: {case.question}"]))[0]
    hits = retrieve_discussion_passages(question=case.question, query_vector=vector,
        passages=passages, query_model=dataset.embedding_model, movie_id=case.movie_id,
        allow_spoilers=True, k=3, on_trace=traces.append)
    answer = await answer_from_hits(client=client, model=dataset.chat_model,
        question=case.question, hits=hits, verify_support=False, on_support_trace=traces.append)
    return hits, answer, traces


async def specialist_answer(client, *, case, passages, dataset):
    hits, traces = [], []
    answer = await answer_movie_question(client, question=case.question, passages=passages,
        movie_id=case.movie_id, allow_spoilers=True, embedding_model=dataset.embedding_model,
        chat_model=dataset.chat_model, on_retrieved=hits.extend, on_retrieval_trace=traces.append)
    return hits, answer, traces


def grade(case, result, error, *, specialist):
    hits, answer, traces = result if result is not None else ([], None, [])
    labelled = MovieRagCase(id=case.id.replace("-", "_"), question=case.question,
        expected_status=case.expected_status, relevant_passage_ids=case.relevant_passage_ids,
        required_phrase_groups=case.required_phrase_groups)
    context = next((trace for trace in traces if trace.get("type") == "context"), None)
    outcome = grade_case(labelled, hits, answer,
        allowed_citation_ids=context["generation_ids"] if specialist and context else None)
    if error is not None and "Generation or response validation failed" not in outcome["failures"]:
        outcome["failures"].append("Generation or response validation failed")
        outcome["automated_pass"] = False
    return hits, answer, traces, outcome


async def run(args):
    if args.output.exists() or args.markdown.exists():
        raise ValueError("Use new output paths for the first frozen benchmark run")
    dataset, sources, dataset_sha = load_frozen_dataset(args.dataset, root=ROOT)
    meter = CallMeter()
    store = EvidenceStore(args.vectors)
    passages = {}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=180,
            trust_env=False, follow_redirects=False,
            event_hooks={"request": [meter.request], "response": [meter.response]}) as client:
        for model in (dataset.embedding_model, dataset.chat_model, discussion_support.MODEL):
            await verify_local_model(client, model)
        for movie_id, source in sources.items():
            state = await ingest_source(client, store=store, source=source,
                model=dataset.embedding_model, **dataset.chunk_settings)
            passages[movie_id] = await asyncio.to_thread(store.load_snapshot, source,
                model=dataset.embedding_model, **dataset.chunk_settings)
            print(f"source {movie_id}: {state}", flush=True)

        rows = []
        for index, case in enumerate(dataset.cases):
            async def direct():
                return await direct_answer(client, case=case, passages=passages[case.movie_id], dataset=dataset)
            async def specialist():
                return await specialist_answer(client, case=case, passages=passages[case.movie_id], dataset=dataset)
            operations = [("direct", direct), ("specialist", specialist)]
            if index % 2:
                operations.reverse()
            measured = {}
            for arm, operation in operations:
                result, error, duration, calls = await meter.measure(arm, operation)
                hits, answer, traces, outcome = grade(case, result, error, specialist=arm == "specialist")
                measured[arm] = {
                    "answer": asdict(answer) if answer else None,
                    "retrieved_ids": [hit.passage.passage_id for hit in hits],
                    "error": error,
                    "duration_seconds": duration,
                    "calls": calls,
                    "grade": outcome,
                    "retrieval_trace": next((trace for trace in traces if trace.get("policy") == discussion_retrieval.POLICY), None),
                    "context_trace": next((trace for trace in traces if trace.get("type") == "context"), None),
                    "support_review": next((trace for trace in traces if trace.get("type") == "support_review"), None),
                }
                print(f"{case.id} {arm}: {'PASS' if outcome['automated_pass'] else 'FAIL'} {duration}s", flush=True)
            rows.append({
                "id": case.id, "movie_id": case.movie_id, "title": case.title,
                "question": case.question, "expected_status": case.expected_status,
                "reference_answer": case.reference_answer,
                "relevant_passage_ids": case.relevant_passage_ids,
                **measured,
            })

    tracked = [discussion_retrieval, discussion_context, grounding_learning, discussion_support]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "direct-vs-specialist-movie-rag-v2" if dataset.policy.endswith("v2")
                  else "direct-vs-specialist-movie-rag-v1",
        "dataset": project_relative_path(args.dataset, root=ROOT),
        "dataset_sha256": dataset_sha,
        "split": dataset.split,
        "label_origin": dataset.label_origin,
        "models": {model: DIGESTS[model] for model in (dataset.embedding_model, dataset.chat_model, discussion_support.MODEL)},
        "pipeline_hashes": {Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() for module in tracked},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "case_order": "Alternating direct-first and specialist-first; arms are sequential.",
        "comparison": comparison(rows),
        "cases": rows,
        "publication": False,
        "limitations": [
            "Labels are frozen and independent of the compared discussion pipelines, but are not independent human annotations.",
            "Exact phrase and citation checks do not prove full semantic entailment; human claim review remains pending.",
            f"{sum(case.expected_status == 'answered' for case in dataset.cases)} answerable and "
            f"{sum(case.expected_status == 'insufficient_evidence' for case in dataset.cases)} "
            "missing-evidence cases are too small for a production accuracy claim.",
            "Sources and embeddings were cached; timings measure local inference/orchestration, not live Internet acquisition.",
            "Local Ollama model switching and host load affect latency. Token counts come from Ollama responses and are not monetary cost.",
            "The comparison evaluates question answering, not the separate fact/quiz drafting and publication workflow.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.markdown.write_text(render_comparison(report))
    print(json.dumps(report["comparison"], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals/movie-rag/orchestration-benchmark/holdout-v1.json")
    parser.add_argument("--vectors", type=Path, default=ROOT / ".cache/orchestration-benchmark/vectors")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/movie-rag/orchestration-benchmark/run-v1.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "evals/movie-rag/orchestration-benchmark/comparison-v1.md")
    try:
        asyncio.run(run(parser.parse_args()))
    except (ValueError, OSError, httpx.HTTPError, TimeoutError) as error:
        raise SystemExit(f"Orchestration benchmark stopped ({type(error).__name__}): {error}") from error
