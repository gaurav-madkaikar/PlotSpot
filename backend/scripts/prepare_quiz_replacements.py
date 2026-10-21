"""Generate and review saved-quiz replacement drafts without publishing them."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_workflow import (
    MODEL, POLICY, build_targets, generate_drafts, review_drafts,
)
from movie_companion.research_checkpoint import digest


def module_hashes():
    root = Path(__file__).resolve().parents[1] / "src" / "movie_companion"
    names = ("quiz_replacement_workflow.py", "structured_content_review.py",
             "content_proposals.py", "quiz_narrative_quality.py",
             "quiz_answer_support.py", "ollama_learning.py", "local_models.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def render_markdown(report):
    totals = report["summary"]
    rows = ["# Saved quiz replacement review", "", f"Generated: {report['generated_at']}", "",
            "**Status: PROPOSAL ONLY — NOTHING PUBLISHED**", "",
            f"- Targets: {totals['targets']}",
            f"- Writer drafts: {totals['writer_drafts']}",
            f"- Deterministic passes: {totals['deterministic_passes']}",
            f"- Critic accepts for assistant review: {totals['critic_accepts']}", "",
            "| Movie | Old question | Candidate | Result |", "|---|---|---|---|"]
    for item in report["items"]:
        candidate = item["candidate"]
        result = ("critic accept" if item["ready_for_assistant_review"] else
                  ", ".join(item["deterministic_problems"]) if item["deterministic_problems"] else
                  item["critic"]["decision"] if item["critic"] else "withheld")
        question = "—" if candidate is None else candidate["question"].replace("|", "\\|")
        rows.append(f"| {item['title']} | {item['old_question'].replace('|','\\|')} | {question} | {result} |")
    rows.extend(["", "## Limits", "",
        "- This workflow cannot publish, delete or replace saved content.",
        "- Local-model acceptance is a review signal, not independent human validation.",
        "- Every accepted draft still needs explicit source, novelty and editorial review before a new publication receipt.",
        ""])
    return "\n".join(rows)


async def run(args):
    review = json.loads(args.review.read_text())
    bank = ContentStore(args.database)
    targets = build_targets(review, bank)
    initial_hashes = module_hashes()
    items = []
    if args.output.is_file():
        checkpoint = json.loads(args.output.read_text())
        if (checkpoint.get("status") == "running" and checkpoint.get("published") is False
                and checkpoint.get("planned") == len(targets)
                and isinstance(checkpoint.get("items"), list)):
            items = checkpoint["items"]
            if len(items) > len(targets) or any(
                item.get("movie_id") != targets[index]["movie_id"]
                or item.get("question_id") != targets[index]["question_id"]
                for index, item in enumerate(items)
            ):
                raise ValueError("Existing checkpoint does not match the replacement plan")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=args.timeout,
                                 trust_env=False, follow_redirects=False) as client:
        await verify_local_model(client, args.model)
        for start in range(len(items), len(targets), args.batch_size):
            batch = targets[start:start + args.batch_size]
            drafts = await generate_drafts(client, targets=batch, model=args.model)
            reviewed = await review_drafts(client, targets=batch, drafts=drafts, model=args.model)
            for row in reviewed:
                target = batch[int(row["target_id"][1:]) - 1]
                items.append({
                    "movie_id": target["movie_id"], "title": target["title"],
                    "question_id": target["question_id"], "old_question": target["old_question"],
                    "replacement_brief": target["replacement_brief"],
                    "evidence": target["evidence"], "bank_version": target["bank_version"],
                    "bank_prepared_at": target["bank_prepared_at"], **{k: v for k, v in row.items() if k != "target_id"},
                })
            partial = {"status": "running", "policy": POLICY, "completed": len(items),
                       "planned": len(targets), "items": items, "published": False}
            atomic_json(args.output, partial)
    if module_hashes() != initial_hashes:
        raise ValueError("Replacement implementation changed during inference")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "status": "proposal_only",
        "published": False,
        "source_review": str(args.review),
        "source_review_sha256": digest(review),
        "database": str(args.database),
        "model": args.model,
        "model_digest": DIGESTS[args.model],
        "implementation_sha256": initial_hashes,
        "summary": {
            "targets": len(items),
            "writer_drafts": sum(item["candidate"] is not None for item in items),
            "deterministic_passes": sum(item["candidate"] is not None and not item["deterministic_problems"] for item in items),
            "critic_accepts": sum(item["ready_for_assistant_review"] for item in items),
        },
        "items": items,
        "publication": {"authorized": False, "database_mutated": False},
    }
    atomic_json(args.output, report)
    args.markdown.write_text(render_markdown(report))
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path,
        default=Path("evals/movie-rag/quiz-narrative-quality/assistant-bank-review-v1.json"))
    parser.add_argument("--database", type=Path, default=Path("data/movie-content.db"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--model", default=MODEL, choices=(MODEL,))
    parser.add_argument("--batch-size", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument("--timeout", type=float, default=180)
    arguments = parser.parse_args()
    if arguments.output.suffix != ".json" or arguments.markdown.suffix != ".md":
        parser.error("Output files must be JSON and Markdown")
    asyncio.run(run(arguments))
