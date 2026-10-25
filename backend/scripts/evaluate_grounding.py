"""Explicit local-only six-case development evaluation, not a safety guarantee."""

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

from movie_companion.grounding_eval import check_answer
from movie_companion.grounding_learning import answer_from_hits, build_grounded_prompt
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/grounding/cases.json"
MODEL = "llama3.2:3b"


async def evaluate(output: Path) -> int:
    dataset_bytes = DATASET.read_bytes()
    dataset = json.loads(dataset_bytes)
    rows = []
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        for case in dataset["cases"]:
            # Fixed selected evidence isolates generation; these vectors are NOT model outputs.
            hits = [RetrievalHit(EmbeddedPassage(
                passage_id=record["passage_id"], movie_id=900000001,
                text=record["text"], vector=[1.0, 0.0],
                embedding_model="not-used-fixed-evidence-fixture",
                source_label=record["source_label"], spoiler_status="safe",
            ), 1.0) for record in case["evidence"]]
            start = time.perf_counter()
            answer, failures, error = None, [], None
            try:
                result = await answer_from_hits(client, model=MODEL, question=case["question"], hits=hits)
                answer = asdict(result)
                failures = check_answer(case, result)
            except (httpx.HTTPError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                failures = ["Generation or validation failed"]
            row = {
                "id": case["id"], "category": case["category"],
                "answer": answer, "automated_pass": not failures,
                "failures": failures, "error": error,
                "duration_seconds": round(time.perf_counter() - start, 3),
                "human_claim_support_review": "pending",
            }
            rows.append(row)
            print(f"{'PASS' if row['automated_pass'] else 'FAIL'} {case['id']}: {row['duration_seconds']}s", flush=True)
    passed = sum(row["automated_pass"] for row in rows)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset["version"], "split": dataset["split"],
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "prompt_source_sha256": hashlib.sha256(inspect.getsource(build_grounded_prompt).encode()).hexdigest(),
        "grounding_boundary_sha256": hashlib.sha256(inspect.getsource(answer_from_hits).encode()).hexdigest(),
        "model": MODEL, "model_digest": None,
        "runtime": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "generation_settings": "Schema-constrained JSON; temperature=0; seed=7; stream=false; no retries; sequential calls",
        "token_usage": None,
        "limitations": [
            "Six development cases; no held-out estimate or universal injection defense claim.",
            "Fixed supplied evidence; embedding/retrieval and tool permissions are not evaluated here.",
            "Keyword and ID checks do not prove factual support; human review remains pending.",
            "chat_once does not return token metadata; model digest is not pinned.",
        ],
        "summary": {
            "automated_passed": passed, "total": len(rows),
            "generation_errors": sum(row["error"] is not None for row in rows),
            "answered_cases": sum(row["answer"] is not None and row["answer"]["status"] == "answered" for row in rows),
            "abstained_cases": sum(row["answer"] is not None and row["answer"]["status"] == "insufficient_evidence" for row in rows),
        },
        "cases": rows
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Automated checks: {passed}/{len(rows)}. Human claim review pending. Report: {output}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evals/grounding/baseline.json")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(evaluate(args.output)))
