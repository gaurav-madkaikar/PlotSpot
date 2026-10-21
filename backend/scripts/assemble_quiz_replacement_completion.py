"""Assemble every reviewed quiz-replacement target into one proposal-only report."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from movie_companion.content_store import ContentStore
from movie_companion.quiz_answer_support import literal_answer_support
from movie_companion.quiz_replacement_completion import (
    NarrativeIntent,
    intent_contract_problems,
    load_completion_manifest,
)
from movie_companion.research_checkpoint import digest


ROOT = Path(__file__).resolve().parents[2]
POLICY = "quiz-replacement-completion-final-v1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def verify_hash(label: str, value: object, expected: str) -> None:
    if canonical_sha256(value) != expected:
        raise ValueError(f"{label} changed")


def exact_scope(original: dict, decisions: list[dict]) -> None:
    expected = {
        (row["movie_id"], row["question_id"])
        for row in original.get("decisions", [])
        if row.get("disposition") == "replace"
    }
    actual = [(row.get("movie_id"), row.get("question_id")) for row in decisions]
    if (
        len(expected) != 34
        or len(actual) != len(set(actual))
        or set(actual) != expected
        or len(actual) != 34
    ):
        raise ValueError("Final replacement decisions do not match original scope")


def build_final_report(decisions: list[dict], input_hashes: dict[str, str], metrics=None):
    ready = sum(row.get("decision") == "ready" for row in decisions)
    withheld = len(decisions) - ready
    reasons = Counter(
        row["withheld_reason"]
        for row in decisions
        if row.get("decision") == "withheld"
    )
    lanes = {}
    for lane in sorted({row.get("lane", "unknown") for row in decisions}):
        rows = [row for row in decisions if row.get("lane", "unknown") == lane]
        lane_ready = sum(row.get("decision") == "ready" for row in rows)
        lanes[lane] = {
            "targets": len(rows),
            "ready": lane_ready,
            "withheld": len(rows) - lane_ready,
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "status": "proposal_only",
        "published": False,
        "input_hashes": input_hashes,
        "summary": {
            "targets": len(decisions),
            "ready": ready,
            "withheld": withheld,
            "withheld_reasons": dict(sorted(reasons.items())),
            "lanes": lanes,
        },
        "metrics": metrics or {},
        "items": sorted(
            decisions, key=lambda row: (row["movie_id"], row["question_id"])
        ),
        "publication": {"authorized": False, "database_mutated": False},
    }


def _load(path: Path):
    return json.loads(path.read_text())


def _identity_map(items, *, name):
    result = {}
    for row in items:
        identity = (row.get("movie_id"), row.get("question_id"))
        if identity in result:
            raise ValueError(f"Duplicate {name} identity")
        result[identity] = row
    return result


def _accepted_novelty(row):
    reviews = row.get("reviews")
    return bool(
        row.get("error_type") is None
        and row.get("ready_for_final_selection") is True
        and isinstance(reviews, list)
        and len(reviews) == 1
        and reviews[0].get("novelty") == "new"
        and reviews[0].get("clarity") == "clear"
    )


def _withheld_from_novelty(row):
    if row.get("error_type"):
        return "novelty_review_error"
    reviews = row.get("reviews") or []
    if any(review.get("novelty") == "duplicate" for review in reviews):
        return "novelty_duplicate"
    if any(review.get("novelty") == "uncertain" for review in reviews):
        return "novelty_uncertain"
    if any(review.get("clarity") != "clear" for review in reviews):
        return "wording_not_clear"
    return "quality_gate_not_passed"


def _validate_candidate(candidate, *, context):
    if not isinstance(candidate, dict):
        raise ValueError(f"{context} candidate is absent")
    options = candidate.get("options")
    correct = candidate.get("correct_index")
    quote = candidate.get("evidence_quote")
    if (
        not isinstance(options, list)
        or len(options) != 4
        or type(correct) is not int
        or not 0 <= correct < 4
        or not isinstance(quote, str)
        or not literal_answer_support(options[correct], quote)
    ):
        raise ValueError(f"{context} grounding changed")


def _validate_review_input(report, packet_path):
    packet_bytes = packet_path.read_bytes()
    if report.get("input_sha256") != sha256_bytes(packet_bytes):
        raise ValueError("Whole-bank input changed")
    packet = json.loads(packet_bytes)
    return _identity_map(packet.get("items", []), name="whole-bank input")


def _validate_selection_source(selection, candidate):
    source_path = ROOT / selection["source_report"]
    source_bytes = source_path.read_bytes()
    if sha256_bytes(source_bytes) != selection["source_report_sha256"]:
        raise ValueError("Editorial source report changed")
    source = json.loads(source_bytes)
    matches = [
        row
        for row in source.get("items", [])
        if row.get("movie_id") == selection["movie_id"]
        and row.get("question_id") == selection["question_id"]
    ]
    if len(matches) != 1 or matches[0].get("final_review") not in (
        "accept",
        "editorial_accept",
    ):
        raise ValueError("Candidate lacks editorial acceptance")
    if matches[0].get("candidate") != candidate:
        raise ValueError("Editorial candidate changed")
    verify_hash("Editorial candidate", candidate, selection["candidate_sha256"])


def _validate_current_bank(store, row):
    saved = store.load(row["movie_id"])
    if saved is None or canonical_sha256(saved["quiz"].model_dump(mode="json")) != row.get(
        "bank_sha256"
    ):
        raise ValueError("Saved quiz bank changed")


def _reviewed_ready_row(row, selection, store):
    candidate = row.get("candidate")
    _validate_candidate(candidate, context="Whole-bank")
    _validate_selection_source(selection, candidate)
    _validate_current_bank(store, row)
    if not _accepted_novelty(row):
        raise ValueError("Ready candidate lacks new and clear novelty review")
    return candidate


def assemble(args):
    source_review = _load(args.source_review)
    if (
        source_review.get("policy") != "assistant-semantic-quiz-bank-review-v1"
        or source_review.get("status") != "proposal_only"
    ):
        raise ValueError("Expected proposal-only source review")
    manifest = load_completion_manifest(args.manifest)
    if digest(source_review) != manifest.source_review_sha256:
        raise ValueError("Source review changed after manifest freeze")

    existing_review = _load(args.existing_whole_bank)
    completion_editorial = _load(args.completion_editorial)
    completion_review = _load(args.completion_whole_bank)
    existing_packet_path = args.existing_whole_bank.parent / "provisional-whole-bank-input-v1.json"
    completion_packet_path = (
        args.completion_whole_bank.parent
        / "replacement-completion-whole-bank-input-v1.json"
    )
    existing_selections = _validate_review_input(existing_review, existing_packet_path)
    completion_selections = _validate_review_input(
        completion_review, completion_packet_path
    )

    candidate_path = ROOT / completion_editorial["source_report"]
    candidate_bytes = candidate_path.read_bytes()
    if sha256_bytes(candidate_bytes) != completion_editorial.get("source_report_sha256"):
        raise ValueError("Completion candidate report changed")
    candidate_report = json.loads(candidate_bytes)
    candidate_rows = _identity_map(candidate_report.get("items", []), name="candidate")
    editorial_rows = _identity_map(
        completion_editorial.get("items", []), name="completion editorial"
    )
    existing_rows = _identity_map(existing_review.get("items", []), name="existing review")
    completion_rows = _identity_map(
        completion_review.get("items", []), name="completion review"
    )
    store = ContentStore(args.database)

    decisions = []
    manifest_rows = {(row.movie_id, row.question_id): row for row in manifest.items}
    for identity, row in existing_rows.items():
        if not _accepted_novelty(row):
            continue
        selection = existing_selections.get(identity)
        if selection is None:
            raise ValueError("Existing ready candidate lacks pinned input")
        candidate = _reviewed_ready_row(row, selection, store)
        decisions.append(
            {
                "movie_id": identity[0],
                "title": next(
                    item["title"]
                    for item in source_review["decisions"]
                    if (item["movie_id"], item["question_id"]) == identity
                ),
                "question_id": identity[1],
                "lane": "existing_ready",
                "decision": "ready",
                "withheld_reason": None,
                "detail": "Previously accepted editorial candidate passed new-and-clear whole-bank review.",
                "candidate": candidate,
                "bank_sha256": row["bank_sha256"],
            }
        )

    for identity, item in manifest_rows.items():
        if item.lane == "novelty":
            row = completion_rows.get(identity)
            selection = completion_selections.get(identity)
            if row is None or selection is None:
                raise ValueError("Novelty lane lacks completion review")
            candidate = row.get("candidate")
            _validate_candidate(candidate, context="Novelty lane")
            _validate_selection_source(selection, candidate)
            _validate_current_bank(store, row)
            ready = _accepted_novelty(row)
            decisions.append(
                {
                    "movie_id": item.movie_id,
                    "title": item.title,
                    "question_id": item.question_id,
                    "lane": item.lane,
                    "decision": "ready" if ready else "withheld",
                    "withheld_reason": None if ready else _withheld_from_novelty(row),
                    "detail": "Independent whole-bank novelty adjudication completed.",
                    "candidate": candidate,
                    "bank_sha256": row["bank_sha256"],
                }
            )
            continue

        editorial = editorial_rows.get(identity)
        generated = candidate_rows.get(identity)
        if editorial is None or generated is None:
            raise ValueError("Generative lane lacks candidate accounting")
        if editorial.get("candidate") != generated.get("candidate"):
            raise ValueError("Editorial candidate changed")
        candidate = editorial.get("candidate")
        final_review = editorial.get("final_review")
        if final_review == "editorial_accept":
            verify_hash("Completion editorial candidate", candidate, editorial["candidate_sha256"])
            _validate_candidate(candidate, context="Completion")
            answer = candidate["options"][candidate["correct_index"]]
            intent = NarrativeIntent.model_validate(generated["intent"])
            if intent_contract_problems(candidate["question"], answer, intent=intent):
                raise ValueError("Completion candidate intent changed")
            row = completion_rows.get(identity)
            selection = completion_selections.get(identity)
            if row is None or selection is None or row.get("candidate") != candidate:
                raise ValueError("Completion editorial accept lacks pinned novelty review")
            _validate_current_bank(store, row)
            ready = _accepted_novelty(row)
            withheld_reason = None if ready else _withheld_from_novelty(row)
        else:
            ready = False
            withheld_reason = (
                generated.get("withheld_reason")
                if final_review == "pipeline_withheld"
                else "editorial_reject"
            ) or "quality_gate_not_passed"
        decisions.append(
            {
                "movie_id": item.movie_id,
                "title": item.title,
                "question_id": item.question_id,
                "lane": item.lane,
                "decision": "ready" if ready else "withheld",
                "withheld_reason": withheld_reason,
                "detail": editorial.get("reason"),
                "candidate": candidate,
                "bank_sha256": item.bank_sha256,
            }
        )

    exact_scope(source_review, decisions)
    recovery_path = (
        args.manifest.parent / "replacement-recovery-evidence-review-v1.json"
    )
    recovery = _load(recovery_path)
    metrics = {
        "evidence_recovery": recovery.get("summary", {}),
        "generation": candidate_report.get("summary", {}),
        "editorial": completion_editorial.get("summary", {}),
        "whole_bank": {
            "existing": existing_review.get("summary", {}),
            "completion": completion_review.get("summary", {}),
        },
        "intent_repair_attempts": sum(
            len(row.get("writer_attempts", [])) > 1
            for row in candidate_report.get("items", [])
        ),
        "recorded_model_seconds": round(
            sum(row.get("seconds", 0) for row in candidate_report.get("items", []))
            + sum(row.get("seconds", 0) for row in existing_review.get("items", []))
            + sum(row.get("seconds", 0) for row in completion_review.get("items", [])),
            3,
        ),
    }
    input_paths = {
        "source_review": args.source_review,
        "manifest": args.manifest,
        "existing_whole_bank": args.existing_whole_bank,
        "completion_editorial": args.completion_editorial,
        "completion_whole_bank": args.completion_whole_bank,
        "candidate_report": candidate_path,
        "recovery_review": recovery_path,
    }
    input_hashes = {
        name: sha256_bytes(path.read_bytes()) for name, path in input_paths.items()
    }
    return build_final_report(decisions, input_hashes, metrics)


def main(args):
    if args.output.exists():
        raise ValueError("Use a new output path")
    report = assemble(args)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--existing-whole-bank", type=Path, required=True)
    parser.add_argument("--completion-editorial", type=Path, required=True)
    parser.add_argument("--completion-whole-bank", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
