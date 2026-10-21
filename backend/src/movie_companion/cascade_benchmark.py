"""Preregistered direct-first composition for the second RAG holdout."""
from copy import deepcopy
import re

from .orchestration_benchmark import summarize_arm


POLICY = "plotspot-direct-first-cascade-v1"
GENERIC_LOCATIONS = (
    "another country", "another place", "a place", "somewhere",
    "a location", "the location", "the area",
)
TIME_UNITS = ("year", "month", "week", "day", "hour", "minute", "second")


def fallback_reason(question: str, sample: dict) -> str | None:
    if sample.get("error") is not None:
        return "direct_generation_or_validation_error"
    answer = sample.get("answer")
    if not isinstance(answer, dict) or answer.get("status") not in ("answered", "insufficient_evidence"):
        return "direct_invalid_response"
    if answer["status"] == "insufficient_evidence":
        return "direct_insufficient_evidence"
    text = str(answer.get("answer", "")).casefold()
    question_text = question.casefold()
    requested_units = [unit for unit in TIME_UNITS if re.search(rf"\b{unit}s?\b", question_text)]
    if re.search(r"\bhow\s+(?:many|long)\b", question_text) and requested_units:
        if not any(re.search(rf"\b{unit}s?\b", text) for unit in requested_units):
            return "requested_time_unit_missing_from_answer"
    if question_text.lstrip().startswith("where") and any(phrase in text for phrase in GENERIC_LOCATIONS):
        return "generic_location_answer"
    return None


def compose_cascade(rows: list[dict]) -> list[dict]:
    composed = []
    for row in rows:
        reason = fallback_reason(row["question"], row["direct"])
        selected = deepcopy(row["specialist"] if reason else row["direct"])
        if reason:
            selected["duration_seconds"] = round(
                row["direct"]["duration_seconds"] + row["specialist"]["duration_seconds"], 3
            )
            selected["calls"] = [*row["direct"]["calls"], *row["specialist"]["calls"]]
        selected["fallback_reason"] = reason
        selected["selected_arm"] = "specialist" if reason else "direct"
        composed.append({**row, "cascade": selected})
    return composed


def compare_cascade(rows: list[dict]) -> dict:
    composed = compose_cascade(rows)
    direct = summarize_arm(composed, "direct")
    specialist = summarize_arm(composed, "specialist")
    cascade = summarize_arm(composed, "cascade")
    reasons = {}
    for row in composed:
        reason = row["cascade"]["fallback_reason"]
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    adopted = (
        cascade["automated_passed"] >= direct["automated_passed"]
        and cascade["missing_evidence_passed"] >= direct["missing_evidence_passed"]
        and cascade["chat_calls"] < specialist["chat_calls"]
    )
    return {
        "direct": direct,
        "specialist": specialist,
        "cascade": cascade,
        "fallbacks": {"count": sum(reasons.values()), "reasons": reasons},
        "cascade_minus_direct_passes": cascade["automated_passed"] - direct["automated_passed"],
        "cascade_minus_specialist_passes": cascade["automated_passed"] - specialist["automated_passed"],
        "cascade_chat_call_savings_vs_specialist": specialist["chat_calls"] - cascade["chat_calls"],
        "decision_rule_passed": adopted,
        "decision": (
            "The preregistered adoption rule passed. Validate with human review and a larger external set before changing production routing."
            if adopted else
            "The preregistered adoption rule did not pass; keep the current production routing unchanged."
        ),
    }


def render_cascade_report(report: dict) -> str:
    comparison = report["comparison"]
    arms = [comparison[name] for name in ("direct", "specialist", "cascade")]
    lines = [
        "# Preregistered direct-first cascade benchmark",
        "",
        f"Dataset SHA-256: `{report['dataset_sha256']}`",
        "",
        "The 30-case holdout and fallback rules were frozen before this run. The cascade reuses the direct answer unless a preregistered trigger fires; fallback cost includes both sequential arms.",
        "",
        "| Metric | Direct | Always specialist | Direct-first cascade |",
        "|---|---:|---:|---:|",
        f"| Automated pass | {arms[0]['automated_passed']}/{arms[0]['cases']} | {arms[1]['automated_passed']}/{arms[1]['cases']} | {arms[2]['automated_passed']}/{arms[2]['cases']} |",
        f"| Answerable pass | {arms[0]['answerable_passed']}/{arms[0]['answerable_total']} | {arms[1]['answerable_passed']}/{arms[1]['answerable_total']} | {arms[2]['answerable_passed']}/{arms[2]['answerable_total']} |",
        f"| Missing-evidence pass | {arms[0]['missing_evidence_passed']}/{arms[0]['missing_evidence_total']} | {arms[1]['missing_evidence_passed']}/{arms[1]['missing_evidence_total']} | {arms[2]['missing_evidence_passed']}/{arms[2]['missing_evidence_total']} |",
        f"| Median latency | {arms[0]['median_latency_seconds']} s | {arms[1]['median_latency_seconds']} s | {arms[2]['median_latency_seconds']} s |",
        f"| P95 latency | {arms[0]['p95_latency_seconds']} s | {arms[1]['p95_latency_seconds']} s | {arms[2]['p95_latency_seconds']} s |",
        f"| Chat calls | {arms[0]['chat_calls']} | {arms[1]['chat_calls']} | {arms[2]['chat_calls']} |",
        f"| Prompt / output tokens | {arms[0]['prompt_tokens']} / {arms[0]['output_tokens']} | {arms[1]['prompt_tokens']} / {arms[1]['output_tokens']} | {arms[2]['prompt_tokens']} / {arms[2]['output_tokens']} |",
        "",
        f"Fallbacks: **{comparison['fallbacks']['count']}** — `{comparison['fallbacks']['reasons']}`",
        "",
        f"**Decision:** {comparison['decision']}",
        "",
        "## Paired outcomes",
        "",
        "| Case | Expected | Direct | Specialist | Cascade | Fallback |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["cases"]:
        status = lambda arm: "pass" if row[arm]["grade"]["automated_pass"] else "fail"
        lines.append(f"| {row['id']} | {row['expected_status']} | {status('direct')} | {status('specialist')} | {status('cascade')} | {row['cascade']['fallback_reason'] or 'none'} |")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)
