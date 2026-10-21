"""Review provisional replacements against every other question in each saved bank."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.content_proposals import QuizProposal
from movie_companion.content_store import ContentStore
from movie_companion.local_models import DIGESTS
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_novelty import POLICY as NOVELTY_POLICY
from movie_companion.quiz_novelty import review_quiz_novelty


ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3.5:9b"
POLICY = "provisional-whole-bank-novelty-review-v1"
ACCEPTED_EDITORIAL_DECISIONS = {"accept", "editorial_accept"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return sha256_bytes(encoded)


def load_candidate(selection: dict) -> tuple[dict, str]:
    required = {
        "source_report",
        "source_report_sha256",
        "movie_id",
        "question_id",
        "candidate_sha256",
    }
    if not isinstance(selection, dict) or set(selection) != required:
        raise ValueError("Invalid provisional selection")
    source_path = ROOT / selection["source_report"]
    source_bytes = source_path.read_bytes()
    if sha256_bytes(source_bytes) != selection["source_report_sha256"]:
        raise ValueError("Editorial source report changed")
    source = json.loads(source_bytes)
    matches = [
        item
        for item in source.get("items", [])
        if item.get("movie_id") == selection["movie_id"]
        and item.get("question_id") == selection["question_id"]
    ]
    if len(matches) != 1:
        raise ValueError("Editorial candidate identity mismatch")
    item = matches[0]
    if item.get("final_review") not in ACCEPTED_EDITORIAL_DECISIONS:
        raise ValueError("Candidate lacks editorial acceptance")
    candidate = item.get("candidate")
    if not isinstance(candidate, dict) or canonical_sha256(candidate) != selection["candidate_sha256"]:
        raise ValueError("Editorial candidate changed")
    return candidate, item.get("old_question", "")


def comparison_bank(quiz, *, replaced_question_id: str) -> tuple[list[dict], str]:
    matches = [item for item in quiz.items if item.id == replaced_question_id]
    if len(matches) != 1:
        raise ValueError("Replacement target is absent from the saved bank")
    existing = [
        {"question": item.question, "answer": item.options[item.correct_index]}
        for item in quiz.items
        if item.id != replaced_question_id
    ]
    return existing, matches[0].question


async def main(args) -> None:
    if args.output.exists():
        raise ValueError("Use a new output path")
    packet_bytes = args.input.read_bytes()
    packet = json.loads(packet_bytes)
    if (
        not isinstance(packet, dict)
        or set(packet) != {"policy", "scope", "items"}
        or packet["policy"] != "provisional-whole-bank-novelty-input-v1"
        or not isinstance(packet["items"], list)
        or not 1 <= len(packet["items"]) <= 12
    ):
        raise ValueError("Invalid provisional review packet")

    store = ContentStore(args.database)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "novelty_policy": NOVELTY_POLICY,
        "input_sha256": sha256_bytes(packet_bytes),
        "model": MODEL,
        "model_digest": DIGESTS[MODEL],
        "scope": packet["scope"],
        "published": False,
        "items": [],
    }
    atomic_json(args.output, report)

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434",
        follow_redirects=False,
        trust_env=False,
        timeout=180,
    ) as client:
        for selection in packet["items"]:
            began = monotonic()
            error_type = None
            review_records: list[dict] = []
            ready = False
            candidate, archived_old_question = load_candidate(selection)
            saved = store.load(selection["movie_id"])
            if saved is None:
                raise ValueError("Movie bank is absent")
            existing, saved_old_question = comparison_bank(
                saved["quiz"], replaced_question_id=selection["question_id"]
            )
            if archived_old_question and archived_old_question != saved_old_question:
                raise ValueError("Saved replacement target changed")
            bank_sha256 = canonical_sha256(saved["quiz"].model_dump(mode="json"))
            proposal = QuizProposal(
                question=candidate["question"],
                options=candidate["options"],
                correct_index=candidate["correct_index"],
                passage_id="P1",
                evidence_quote=candidate["evidence_quote"],
            )
            try:
                reviews = await review_quiz_novelty(
                    client, candidates=[proposal], existing=existing, model=MODEL
                )
                review_records = [review.record() for review in reviews]
                ready = bool(
                    len(reviews) == 1
                    and reviews[0].novelty == "new"
                    and reviews[0].clarity == "clear"
                )
            except (ValueError, httpx.HTTPError, TimeoutError) as exc:
                error_type = type(exc).__name__
            current = store.load(selection["movie_id"])
            if current is None or canonical_sha256(
                current["quiz"].model_dump(mode="json")
            ) != bank_sha256:
                raise ValueError("Saved quiz bank changed during review")
            row = {
                "movie_id": selection["movie_id"],
                "question_id": selection["question_id"],
                "source_report": selection["source_report"],
                "candidate": candidate,
                "replaced_question": saved_old_question,
                "comparison_question_count": len(existing),
                "bank_sha256": bank_sha256,
                "ready_for_final_selection": ready and error_type is None,
                "reviews": review_records,
                "error_type": error_type,
                "seconds": round(monotonic() - began, 3),
            }
            report["items"].append(row)
            atomic_json(args.output, report)
            print(
                f"{'READY' if row['ready_for_final_selection'] else 'WITHHELD'} "
                f"{selection['movie_id']} {selection['question_id']}",
                flush=True,
            )

    report["summary"] = {
        "reviewed": len(report["items"]),
        "ready_for_final_selection": sum(
            item["ready_for_final_selection"] for item in report["items"]
        ),
        "errors": sum(item["error_type"] is not None for item in report["items"]),
    }
    atomic_json(args.output, report)
    print(report["summary"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT
        / "evals/movie-rag/quiz-narrative-quality/provisional-whole-bank-input-v1.json",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="New proposal-only JSON report"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "data/movie-content.db",
    )
    asyncio.run(main(parser.parse_args()))
