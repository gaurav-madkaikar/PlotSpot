"""Reproducible integrity and source-coverage audit for reviewed movie banks."""
from datetime import datetime, timezone
import hashlib
import json

from .content_store import ContentStore
from .research_checkpoint import digest
from .source_coverage import content_coverage


POLICY = "published-content-integrity-audit-v1"


def _payload_sha256(saved) -> str:
    payload = json.dumps({
        "quiz": saved["quiz"].model_dump(),
        "facts": saved["facts"].model_dump(),
        "source_manifest": saved["source_manifest"],
    })
    return hashlib.sha256(payload.encode()).hexdigest()


def _indexed(records, key, label):
    if not isinstance(records, list) or not records:
        raise ValueError(f"Missing {label}")
    result = {}
    for record in records:
        identity = record.get(key) if isinstance(record, dict) else None
        if identity is None or identity in result:
            raise ValueError(f"Invalid {label} identity")
        result[identity] = record
    return result


def audit_published_content(*, review_audit: dict, publication_log: dict,
                            bank: ContentStore) -> dict:
    """Verify publication receipts, payload hashes, quotas and publisher diversity."""
    if review_audit.get("policy") != "assistant-source-review-prepublication-v1":
        raise ValueError("Unsupported review audit")
    if publication_log.get("policy") != "reviewed-research-publication-v1":
        raise ValueError("Unsupported publication log")
    if publication_log.get("review_audit_sha256") != digest(review_audit):
        raise ValueError("Publication log does not identify this review audit")

    reviewed = _indexed(review_audit.get("movies"), "movie_id", "reviewed movie")
    receipts = _indexed(publication_log.get("receipts"), "movie_id", "publication receipt")
    if (set(reviewed) != set(receipts)
            or review_audit.get("movie_count") != len(reviewed)
            or publication_log.get("movie_count") != len(receipts)
            or publication_log.get("all_published") is not True):
        raise ValueError("Review and publication movie sets differ")

    movies = []
    publishers = set()
    totals = {"facts": 0, "quiz_items": 0, "scored_questions": 0,
              "interpretation_prompts": 0, "citations": 0}
    for movie_id, review in reviewed.items():
        receipt = receipts[movie_id]
        if (receipt.get("movie_id") != movie_id
                or receipt.get("job_id") != review.get("job_id")
                or receipt.get("report_sha256") != review.get("report_sha256")):
            raise ValueError(f"Movie {movie_id} receipt does not match its review")
        stored_receipt = bank.receipt(receipt["job_id"])
        if stored_receipt != receipt:
            raise ValueError(f"Movie {movie_id} stored receipt differs from the audit log")
        saved = bank.load(movie_id)
        if saved is None:
            raise ValueError(f"Movie {movie_id} has no published collection")
        coverage = content_coverage(saved["quiz"], saved["facts"])
        if not coverage["complete"]:
            raise ValueError(f"Movie {movie_id} does not satisfy published coverage")
        scored = [item for item in saved["quiz"].items if item.kind != "interpretation"]
        interpretations = len(saved["quiz"].items) - len(scored)
        if (len(saved["facts"].items) != review.get("combined_facts")
                or len(scored) != review.get("combined_questions")):
            raise ValueError(f"Movie {movie_id} content counts differ from review")
        if (saved["version"] != receipt.get("version")
                or saved["prepared_at"] != receipt.get("prepared_at")
                or _payload_sha256(saved) != receipt.get("payload_sha256")):
            raise ValueError(f"Movie {movie_id} published payload differs from its receipt")

        citations = sum(len(item.citations) for item in [*saved["facts"].items, *saved["quiz"].items])
        fact_publishers = coverage["facts"]["publishers"]
        quiz_publishers = coverage["quiz"]["publishers"]
        publishers.update(fact_publishers); publishers.update(quiz_publishers)
        totals["facts"] += len(saved["facts"].items)
        totals["quiz_items"] += len(saved["quiz"].items)
        totals["scored_questions"] += len(scored)
        totals["interpretation_prompts"] += interpretations
        totals["citations"] += citations
        movies.append({
            "movie_id": movie_id,
            "title": review.get("title", str(movie_id)),
            "version": saved["version"],
            "facts": len(saved["facts"].items),
            "scored_questions": len(scored),
            "interpretation_prompts": interpretations,
            "citations": citations,
            "fact_publishers": fact_publishers,
            "quiz_publishers": quiz_publishers,
            "receipt_verified": True,
            "payload_verified": True,
            "coverage_complete": True,
        })

    movies.sort(key=lambda item: list(reviewed).index(item["movie_id"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "status": "pass",
        "scope": "Published-bank integrity, minimum content readiness and citation publisher diversity.",
        "movie_count": len(movies),
        "metrics": {
            **totals,
            "unique_publishers": len(publishers),
            "publishers": sorted(publishers),
            "minimum_facts_per_movie": min(movie["facts"] for movie in movies),
            "minimum_scored_questions_per_movie": min(movie["scored_questions"] for movie in movies),
            "movies_with_multi_publisher_facts": sum(len(movie["fact_publishers"]) >= 2 for movie in movies),
            "movies_with_multi_publisher_quiz": sum(len(movie["quiz_publishers"]) >= 2 for movie in movies),
            "verified_receipts": len(movies),
            "verified_payloads": len(movies),
        },
        "movies": movies,
        "limitations": [
            "This audit does not measure whether every claim or answer is semantically correct.",
            "Publisher diversity does not prove source independence, credibility or agreement.",
            "The reviewed selections were assistant-inspected; independent human labels remain pending.",
            "Latency, throughput, model cost and live provider availability are outside this audit.",
        ],
    }


def render_markdown(report: dict) -> str:
    metrics = report["metrics"]
    rows = [
        "# Published movie-content audit",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Status: {report['status'].upper()}**",
        "",
        report["scope"],
        "",
        "## Measured results",
        "",
        f"- Movies: {report['movie_count']}",
        f"- Facts: {metrics['facts']}",
        f"- Quiz items: {metrics['quiz_items']} ({metrics['scored_questions']} scored, {metrics['interpretation_prompts']} interpretation)",
        f"- Citations: {metrics['citations']}",
        f"- Distinct publisher families: {metrics['unique_publishers']}",
        f"- Receipt and payload checks: {metrics['verified_receipts']}/{report['movie_count']}",
        f"- Multi-publisher fact coverage: {metrics['movies_with_multi_publisher_facts']}/{report['movie_count']}",
        f"- Multi-publisher quiz coverage: {metrics['movies_with_multi_publisher_quiz']}/{report['movie_count']}",
        "",
        "## Per-movie coverage",
        "",
        "| Movie | Facts | Scored quiz | Fact publishers | Quiz publishers |",
        "|---|---:|---:|---|---|",
    ]
    rows.extend(
        f"| {movie['title']} | {movie['facts']} | {movie['scored_questions']} | "
        f"{', '.join(movie['fact_publishers'])} | {', '.join(movie['quiz_publishers'])} |"
        for movie in report["movies"]
    )
    rows.extend(["", "## Limits", ""])
    rows.extend(f"- {limitation}" for limitation in report["limitations"])
    rows.append("")
    return "\n".join(rows)
