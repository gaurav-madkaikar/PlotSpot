"""Generate proposal-only, intent-bound quiz replacements in durable batches."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_completion import (
    load_completion_manifest,
    load_intent_contracts,
)
from movie_companion.quiz_replacement_span_writer import (
    MODEL,
    answer_spans,
    generate_locked_drafts,
)
from movie_companion.quiz_replacement_workflow import build_targets, review_drafts
from movie_companion.quiz_replacement_workflow import ReplacementDraft, ReplacementDrafts
from movie_companion.research_checkpoint import digest


POLICY = "quiz-replacement-completion-candidates-v1"
PIPELINE_REVISION = "bounded-intent-repair-v1"
IDENTITY_KEYS = (
    "policy",
    "pipeline_revision",
    "manifest_sha256",
    "contracts_sha256",
    "source_review_sha256",
    "evidence_review_sha256",
    "recovered_evidence_review_sha256",
    "model",
    "model_digest",
    "planned",
)
INTENT_PROBLEMS = {
    "missing_required_concept",
    "forbidden_detail",
    "answer_shape_mismatch",
}


def resume_rows(path, identity):
    if not path.is_file():
        return []
    checkpoint = json.loads(path.read_text())
    if checkpoint.get("status") != "running" or any(
        checkpoint.get(key) != value for key, value in identity.items()
    ):
        raise ValueError("Completion checkpoint identity changed")
    rows = checkpoint.get("items")
    if not isinstance(rows, list):
        raise ValueError("Invalid completion checkpoint rows")
    identities = [row.get("question_id") for row in rows]
    if any(not isinstance(value, str) for value in identities) or len(identities) != len(
        set(identities)
    ):
        raise ValueError("Duplicate completion checkpoint target")
    return rows


def _withheld_reason(problems, review):
    if any(problem in INTENT_PROBLEMS for problem in problems):
        return "intent_contract_not_satisfied"
    if problems:
        return problems[0]
    if review is None or review.get("candidate") is None:
        return "writer_abstained"
    if not review.get("ready_for_assistant_review"):
        return "critic_rejected"
    return None


def _result_row(target, alias, writer_info, review, *, seconds, error_type=None):
    details = writer_info.get(alias, {"answer_spans": [], "writer_problems": []})
    problems = list(details.get("writer_problems", []))
    if review is not None:
        problems.extend(review.get("deterministic_problems", []))
    problems = list(dict.fromkeys(problems))
    return {
        "movie_id": target["movie_id"],
        "title": target["title"],
        "question_id": target["question_id"],
        "old_question": target["old_question"],
        "replacement_brief": target["replacement_brief"],
        "intent": target["intent"],
        "reviewed_evidence": target["evidence"],
        "answer_spans": details.get("answer_spans", []),
        "writer_attempts": details.get("writer_attempts", []),
        "rejected_candidate": details.get("rejected_candidate"),
        "candidate": None if review is None else review.get("candidate"),
        "deterministic_problems": problems,
        "critic": None if review is None else review.get("critic"),
        "ready_for_assistant_review": bool(
            review is not None
            and review.get("ready_for_assistant_review")
            and not problems
            and error_type is None
        ),
        "withheld_reason": (
            error_type
            or _withheld_reason(problems, review)
        ),
        "error_type": error_type,
        "seconds": round(seconds, 3),
    }


async def run_batch(client, targets):
    if not isinstance(targets, list) or not 1 <= len(targets) <= 3:
        raise ValueError("Run one to three completion targets")
    began = monotonic()
    try:
        drafts, writer_info = await generate_locked_drafts(client, targets)
        draft_by_alias = {draft.target_id: draft for draft in drafts.items}
        for index, target in enumerate(targets):
            alias = f"T{index + 1}"
            first = writer_info[alias]
            repairable = (
                any(problem in INTENT_PROBLEMS for problem in first["writer_problems"])
                and first.get("rejected_candidate") is not None
            )
            if not repairable:
                first["writer_attempts"] = [{
                    "attempt": "initial",
                    "problems": list(first["writer_problems"]),
                    "rejected_candidate": first.get("rejected_candidate"),
                }]
                continue
            feedback = {
                "T1": {
                    "problems": list(first["writer_problems"]),
                    "rejected_candidate": first["rejected_candidate"],
                }
            }
            try:
                repaired_drafts, repaired_info = await generate_locked_drafts(
                    client, [target], repair_feedback=feedback
                )
            except (ValueError, httpx.HTTPError, TimeoutError) as error:
                first["writer_attempts"] = [
                    {"attempt": "initial", "problems": list(first["writer_problems"]),
                     "rejected_candidate": first.get("rejected_candidate")},
                    {"attempt": "repair", "problems": [type(error).__name__],
                     "rejected_candidate": None},
                ]
                continue
            repaired = repaired_info["T1"]
            repaired["writer_attempts"] = [
                {"attempt": "initial", "problems": list(first["writer_problems"]),
                 "rejected_candidate": first.get("rejected_candidate")},
                {"attempt": "repair", "problems": list(repaired["writer_problems"]),
                 "rejected_candidate": repaired.get("rejected_candidate")},
            ]
            writer_info[alias] = repaired
            if repaired_drafts.items:
                value = repaired_drafts.items[0]
                draft_by_alias[alias] = ReplacementDraft(
                    **{**value.model_dump(), "target_id": alias}
                )
        drafts = ReplacementDrafts(
            items=[draft_by_alias[alias] for alias in sorted(
                draft_by_alias, key=lambda value: int(value[1:])
            )]
        )
        reviewed = await review_drafts(client, targets=targets, drafts=drafts)
    except (ValueError, httpx.HTTPError, TimeoutError) as error:
        if len(targets) > 1:
            rows = []
            for target in targets:
                rows.extend(await run_batch(client, [target]))
            return rows
        return [
            _result_row(
                targets[0],
                "T1",
                {"T1": {"answer_spans": [], "writer_problems": []}},
                None,
                seconds=monotonic() - began,
                error_type=type(error).__name__,
            )
        ]
    by_alias = {row["target_id"]: row for row in reviewed}
    rows = []
    for index, target in enumerate(targets):
        alias = f"T{index + 1}"
        rows.append(
            _result_row(
                target,
                alias,
                writer_info,
                by_alias.get(alias),
                seconds=monotonic() - began,
            )
        )
    return rows


def build_report(identity, rows):
    if len(rows) != identity["planned"]:
        raise ValueError("Completion report does not cover every planned target")
    question_ids = [row["question_id"] for row in rows]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Duplicate completion report target")
    return {
        **identity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "proposal_only",
        "published": False,
        "summary": {
            "targets": len(rows),
            "writer_drafts": sum(row.get("candidate") is not None for row in rows),
            "deterministic_passes": sum(
                row.get("candidate") is not None
                and not row.get("deterministic_problems")
                for row in rows
            ),
            "critic_accepts": sum(
                bool(row.get("ready_for_assistant_review")) for row in rows
            ),
            "errors": sum(row.get("error_type") is not None for row in rows),
            "withheld_reasons": dict(
                sorted(
                    {
                        reason: sum(row.get("withheld_reason") == reason for row in rows)
                        for reason in {
                            row.get("withheld_reason") for row in rows if row.get("withheld_reason")
                        }
                    }.items()
                )
            ),
        },
        "items": rows,
        "publication": {"authorized": False, "database_mutated": False},
    }


def _reviewed_evidence(payload, *, policy, name):
    if (
        not isinstance(payload, dict)
        or payload.get("policy") != policy
        or payload.get("status") != "proposal_only"
        or payload.get("published") is not False
        or not isinstance(payload.get("items"), list)
    ):
        raise ValueError(f"Expected proposal-only {name}")
    result = {}
    for row in payload["items"]:
        identity = (row.get("movie_id"), row.get("question_id"))
        if identity in result:
            raise ValueError(f"Duplicate {name} target")
        decision = row.get("editorial_decision")
        if decision not in ("accept", "reject"):
            raise ValueError(f"Invalid {name} decision")
        selected = row.get("selected_evidence")
        if not isinstance(selected, list) or (decision == "accept" and not selected):
            raise ValueError(f"Invalid {name} evidence selection")
        result[identity] = row
    return result


def _citations(selection):
    return [
        {
            key: item[key]
            for key in ("source_label", "source_ref", "revision", "excerpt")
        }
        for item in selection["selected_evidence"]
    ]


def _checkpoint(identity, rows):
    return {
        **identity,
        "status": "running",
        "published": False,
        "items": rows,
        "publication": {"authorized": False, "database_mutated": False},
    }


async def run(args):
    manifest = load_completion_manifest(args.manifest)
    contracts_payload = json.loads(args.contracts.read_text())
    contracts = load_intent_contracts(args.contracts, manifest=manifest)
    source_review = json.loads(args.source_review.read_text())
    original_payload = json.loads(args.original_evidence_review.read_text())
    recovered_payload = json.loads(args.recovered_evidence_review.read_text())
    if digest(source_review) != manifest.source_review_sha256:
        raise ValueError("Source review changed after manifest freeze")
    if digest(original_payload) != manifest.evidence_review_sha256:
        raise ValueError("Original evidence review changed after manifest freeze")
    original = _reviewed_evidence(
        original_payload,
        policy="assistant-replacement-evidence-editorial-v1",
        name="original evidence review",
    )
    recovered = _reviewed_evidence(
        recovered_payload,
        policy="assistant-quiz-replacement-recovery-evidence-v1",
        name="recovered evidence review",
    )
    identity = {
        "policy": POLICY,
        "pipeline_revision": PIPELINE_REVISION,
        "manifest_sha256": digest(manifest.model_dump(mode="json")),
        "contracts_sha256": digest(contracts_payload),
        "source_review_sha256": digest(source_review),
        "evidence_review_sha256": digest(original_payload),
        "recovered_evidence_review_sha256": digest(recovered_payload),
        "model": MODEL,
        "model_digest": DIGESTS[MODEL],
        "planned": 30,
    }
    rows = resume_rows(args.output, identity)
    completed = {row["question_id"] for row in rows}
    store = ContentStore(args.database)
    source_targets = {
        (target["movie_id"], target["question_id"]): target
        for target in build_targets(source_review, store)
    }
    pending = []
    for item in manifest.items:
        if item.lane == "novelty" or item.question_id in completed:
            continue
        source = source_targets[(item.movie_id, item.question_id)]
        selection = (
            original.get((item.movie_id, item.question_id))
            if item.lane == "intent"
            else recovered.get((item.movie_id, item.question_id))
        )
        if selection is None or selection["editorial_decision"] != "accept":
            rows.append(
                {
                    "movie_id": item.movie_id,
                    "title": item.title,
                    "question_id": item.question_id,
                    "old_question": item.old_question,
                    "replacement_brief": item.replacement_brief,
                    "intent": contracts[item.question_id].model_dump(mode="json"),
                    "reviewed_evidence": {"citations": []},
                    "answer_spans": [],
                    "candidate": None,
                    "deterministic_problems": ["insufficient_narrative_evidence"],
                    "critic": None,
                    "ready_for_assistant_review": False,
                    "withheld_reason": "insufficient_narrative_evidence",
                    "error_type": None,
                    "seconds": 0.0,
                }
            )
            atomic_json(args.output, _checkpoint(identity, rows))
            continue
        target = {
            **source,
            "intent": contracts[item.question_id].model_dump(mode="json"),
            "evidence": {
                "explanation": item.replacement_brief,
                "citations": _citations(selection),
            },
        }
        spans = answer_spans(target)
        if not spans:
            rows.append(
                _result_row(
                    target,
                    "T1",
                    {"T1": {"answer_spans": [], "writer_problems": ["no_natural_exact_answer_span"]}},
                    None,
                    seconds=0.0,
                )
            )
            atomic_json(args.output, _checkpoint(identity, rows))
            continue
        pending.append(target)

    if pending:
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:11434",
            timeout=args.timeout,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            await verify_local_model(client, MODEL)
            for start in range(0, len(pending), 3):
                rows.extend(await run_batch(client, pending[start : start + 3]))
                atomic_json(args.output, _checkpoint(identity, rows))
    report = build_report(identity, rows)
    atomic_json(args.output, report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--original-evidence-review", type=Path, required=True)
    parser.add_argument("--recovered-evidence-review", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/movie-content.db"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    asyncio.run(run(parser.parse_args()))
