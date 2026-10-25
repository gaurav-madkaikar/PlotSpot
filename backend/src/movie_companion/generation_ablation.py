"""Audit the writer -> critic -> readiness -> reviewed-publication funnel."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


POLICY = "plotspot-generation-orchestration-ablation-v1"
KINDS = ("fact", "question")
DECISIONS = ("accept", "reject", "uncertain")


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


def _summary(rows: list[dict]) -> dict:
    direct = len(rows)
    critic = sum(row["decision"] == "accept" for row in rows)
    ready = sum(row["ready"] for row in rows)
    published = sum(row["retained"] for row in rows)
    return {
        "writer_candidates": direct,
        "critic_accepted": critic,
        "specialist_ready": ready,
        "reviewed_published": published,
        "critic_reduction_percent": _percent(direct - critic, direct),
        "full_pipeline_workload_reduction_percent": _percent(direct - ready, direct),
        "readiness_reduction_after_critic_percent": _percent(critic - ready, critic),
        "published_conversion_from_writer_percent": _percent(published, direct),
        "published_conversion_from_ready_percent": _percent(published, ready),
        "reviewed_published_retained_by_critic": sum(
            row["retained"] and row["decision"] == "accept" for row in rows
        ),
        "reviewed_published_retained_by_readiness": sum(
            row["retained"] and row["ready"] for row in rows
        ),
        "critic_decisions": dict(sorted(Counter(row["decision"] for row in rows).items())),
        "ready_not_published": sum(row["ready"] and not row["retained"] for row in rows),
    }


def analyze_generation_exports(exports: list[tuple[Path, dict]]) -> dict:
    if not exports:
        raise ValueError("At least one reviewed generation export is required")
    rows, inputs, movies = [], [], set()
    for path, export in exports:
        movie_id = export.get("movie_id")
        candidates = export.get("all_candidates")
        if type(movie_id) is not int or movie_id <= 0 or movie_id in movies:
            raise ValueError("Generation exports need unique positive movie IDs")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Generation export has no candidates")
        movies.add(movie_id)
        candidate_ids = set()
        for candidate in candidates:
            identifier = candidate.get("id")
            kind = candidate.get("kind")
            decision = candidate.get("decision")
            ready = candidate.get("ready")
            retained = candidate.get("retained")
            if (not isinstance(identifier, str) or not identifier or identifier in candidate_ids
                    or kind not in KINDS or decision not in DECISIONS
                    or type(ready) is not bool or type(retained) is not bool):
                raise ValueError(f"Invalid candidate funnel state for movie {movie_id}")
            if retained and (not ready or decision != "accept"):
                raise ValueError("Published candidates must survive critic and readiness stages")
            if ready and decision != "accept":
                raise ValueError("Ready candidates must have an accepting critic decision")
            candidate_ids.add(identifier)
            rows.append({
                "movie_id": movie_id,
                "id": identifier,
                "kind": kind,
                "decision": decision,
                "ready": ready,
                "retained": retained,
            })
        raw = path.read_bytes()
        if json.loads(raw) != export:
            raise ValueError("Export bytes and parsed payload differ")
        inputs.append({
            "path": str(path),
            "sha256": sha256(raw).hexdigest(),
            "movie_id": movie_id,
            "report_sha256": export.get("report_sha256"),
            "candidates": len(candidates),
        })
    summary = _summary(rows)
    return {
        "policy": POLICY,
        "input_movies": len(movies),
        "inputs": sorted(inputs, key=lambda item: item["movie_id"]),
        "comparison": {
            "direct_writer": {
                "outputs_requiring_review": summary["writer_candidates"],
                "known_published_items_present": summary["reviewed_published"],
            },
            "writer_plus_critic": {
                "outputs_requiring_review": summary["critic_accepted"],
                "known_published_items_present": summary["reviewed_published_retained_by_critic"],
            },
            "writer_plus_critic_and_readiness": {
                "outputs_requiring_review": summary["specialist_ready"],
                "known_published_items_present": summary["reviewed_published_retained_by_readiness"],
            },
        },
        "overall": summary,
        "by_kind": {kind: _summary([row for row in rows if row["kind"] == kind]) for kind in KINDS},
        "publication": False,
        "interpretation": (
            "The full specialist pipeline substantially reduced candidate-review workload while retaining every "
            "candidate later selected for reviewed publication. The critic alone contributed little reduction; "
            "readiness, novelty and corroboration gates did most of the filtering."
        ),
        "limitations": [
            "Reviewed publication selection is a high-confidence positive set, not a complete good/bad label for every unselected candidate.",
            "Published conversion is not semantic precision because valid candidates may be omitted for capacity or topic overlap.",
            "The arms reuse the same writer candidates; this isolates downstream filtering rather than comparing two independent generations.",
            "Historical per-call latency and token totals are not comparable across the durable jobs and are excluded.",
            "Assistant source review is not independent human annotation; a blinded candidate review remains required for semantic quality.",
        ],
    }


def render_generation_ablation(report: dict) -> str:
    overall = report["overall"]
    fact = report["by_kind"]["fact"]
    question = report["by_kind"]["question"]
    lines = [
        "# Fact and quiz generation orchestration ablation",
        "",
        f"Frozen reviewed exports: **{report['input_movies']} movies**",
        "",
        "All rows start with the same researcher evidence and writer candidates. The ablation removes or adds downstream critic/readiness stages, so evidence and drafts stay paired.",
        "",
        "| Funnel stage | All | Facts | Quiz questions |",
        "|---|---:|---:|---:|",
        f"| Writer candidates | {overall['writer_candidates']} | {fact['writer_candidates']} | {question['writer_candidates']} |",
        f"| Critic accepted | {overall['critic_accepted']} | {fact['critic_accepted']} | {question['critic_accepted']} |",
        f"| Full specialist ready | {overall['specialist_ready']} | {fact['specialist_ready']} | {question['specialist_ready']} |",
        f"| Reviewed publication selection | {overall['reviewed_published']} | {fact['reviewed_published']} | {question['reviewed_published']} |",
        f"| Ready but not selected | {overall['ready_not_published']} | {fact['ready_not_published']} | {question['ready_not_published']} |",
        "",
        "| Operational comparison | Result |",
        "|---|---:|",
        f"| Critic-only workload reduction | {overall['critic_reduction_percent']}% |",
        f"| Full-pipeline workload reduction | {overall['full_pipeline_workload_reduction_percent']}% |",
        f"| Additional reduction after critic | {overall['readiness_reduction_after_critic_percent']}% |",
        f"| Published conversion from all writer candidates | {overall['published_conversion_from_writer_percent']}% |",
        f"| Published conversion from ready candidates | {overall['published_conversion_from_ready_percent']}% |",
        f"| Published items lost by full specialist pipeline | {overall['reviewed_published'] - overall['reviewed_published_retained_by_readiness']} |",
        "",
        f"**Observed comparison:** {report['interpretation']}",
        "",
        "## What this does and does not measure",
        "",
        "The direct baseline would send every structurally valid writer candidate to manual review. The critic-only arm sends critic accepts. The full specialist arm also applies citation completeness, semantic support, saved-topic novelty, clarity and corroboration/readiness checks.",
        "",
        "The reviewed publication set establishes known good retained items. An unselected item may still be valid, so the conversion values above describe the review funnel and are not accuracy or precision claims.",
        "",
        "## Limits",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)
