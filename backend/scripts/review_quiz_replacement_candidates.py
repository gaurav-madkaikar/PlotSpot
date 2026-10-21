"""Record the assistant editorial review of generated quiz replacements."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from movie_companion.preparation_jobs import atomic_json
from movie_companion.research_checkpoint import digest


POLICY = "assistant-editorial-quiz-replacement-review-v1"
EDITORIAL = {
    "research-423740447f00-t1-Q2": ("reject", "The selected answer copies the whole evidence sentence and retains the exact duration the brief asked to omit."),
    "research-423740447f00-t6-Q2": ("reject", "The selected answer copies a complete source sentence instead of giving the concise relationship revelation."),
    "research-e783e7f83fe0-t24-Q2": ("reject", "The answer does not directly explain how Bob links the two parts of the Narrator's life."),
    "research-6bd2d9de6c13-t10-Q1": ("reject", "The evidence states Borden's family structure but not the claimed impact of his double life."),
    "research-b4c4933bed48-t11-Q3": ("accept", "The question tests the central threat to Simba's future rule, the answer is concise enough, and the exact evidence supports it."),
    "research-a7b58936b8bc-t10-Q3": ("reject", "The question only asks what happens and does not test the reconciliation's effect on protecting the plant as requested."),
    "script-rag-74e285b37039": ("reject", "The answer retains the exact Limbo duration and does not test Mal's lasting belief as requested."),
    "research-600f039b5e2b-t6-Q2": ("reject", "The answer retains the exact Vuvalini count the replacement brief explicitly asked to omit."),
    "research-600f039b5e2b-t8-Q1": ("reject", "The generic action stem still tests the same narrow overtake detail and not its effect on the escape."),
}


def render(report):
    rows = ["# Editorial review of quiz replacement candidates", "",
            f"Generated: {report['generated_at']}", "",
            "**Status: PROPOSAL ONLY — NOTHING PUBLISHED**", "",
            f"- Replacement targets: {report['summary']['targets']}",
            f"- Withheld by code or critic: {report['summary']['pipeline_withheld']}",
            f"- Editorial rejects: {report['summary']['editorial_rejects']}",
            f"- Editorially ready for a later publication review: {report['summary']['editorial_accepts']}", "",
            "| Movie | Candidate | Final review | Reason |", "|---|---|---|---|"]
    for item in report["items"]:
        candidate = item["candidate"]
        question = "—" if candidate is None else candidate["question"].replace("|", "\\|")
        rows.append(f"| {item['title']} | {question} | {item['final_review']} | {item['reason'].replace('|','\\|')} |")
    rows.extend(["", "The single editorial acceptance is still not authorized for publication. It must be combined with a complete replacement set, rechecked against the then-current bank, and receive a new atomic publication receipt.", ""])
    return "\n".join(rows)


def main(args):
    source = json.loads(args.input.read_text())
    if (source.get("policy") != "saved-quiz-replacement-workflow-v1"
            or source.get("status") != "proposal_only" or source.get("published") is not False
            or len(source.get("items", [])) != 34):
        raise ValueError("Expected the complete non-publishing replacement report")
    critic_ready = {item["question_id"] for item in source["items"] if item["ready_for_assistant_review"]}
    if critic_ready != set(EDITORIAL):
        raise ValueError("Editorial decisions do not match the critic-ready candidate set")
    rows = []
    for item in source["items"]:
        if item["question_id"] in EDITORIAL:
            verdict, reason = EDITORIAL[item["question_id"]]
        elif item["deterministic_problems"]:
            verdict = "withheld_by_code"
            reason = ", ".join(item["deterministic_problems"])
        else:
            verdict = "withheld_by_critic"
            reason = item["critic"]["reason"]
        rows.append({
            "movie_id": item["movie_id"], "title": item["title"],
            "question_id": item["question_id"], "old_question": item["old_question"],
            "candidate": item["candidate"], "final_review": verdict, "reason": reason,
        })
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "status": "proposal_only",
        "published": False,
        "source_report": str(args.input),
        "source_report_sha256": digest(source),
        "summary": {
            "targets": len(rows),
            "pipeline_withheld": sum(row["final_review"].startswith("withheld") for row in rows),
            "editorial_rejects": sum(row["final_review"] == "reject" for row in rows),
            "editorial_accepts": sum(row["final_review"] == "accept" for row in rows),
        },
        "items": rows,
        "publication": {"authorized": False, "database_mutated": False},
    }
    atomic_json(args.output, report)
    args.markdown.write_text(render(report))
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    arguments = parser.parse_args()
    main(arguments)
