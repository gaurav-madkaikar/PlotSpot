"""Normalize registered evaluation reports without inventing common scores."""

from datetime import datetime, timezone
import math
from typing import Any, Protocol

from .lab_contracts import LabMetric, LabSuite


class SuiteSpec(Protocol):
    id: str
    title: str
    feature: str
    category: str
    relative_path: str
    gated: bool


def _dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {field}")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"Invalid {field}")
    return value


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {field}")
    return value


def _float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid {field}")
    result = float(value)
    if result < 0 or not math.isfinite(result):
        raise ValueError(f"Invalid {field}")
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {field}")
    return value


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError("Invalid timestamp")
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _limitations(value: Any, fallback: str) -> list[str]:
    if value is None:
        values = [fallback]
    elif isinstance(value, str):
        values = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        values = value
    else:
        raise ValueError("Invalid limitations")
    clean = [" ".join(item.split())[:500] for item in values if item.strip()]
    return clean[:12] or [fallback]


def _count(identifier: str, label: str, value: Any, definition: str, *, direction="neutral"):
    number = _int(value, identifier)
    return LabMetric(
        id=identifier,
        label=label,
        value=number,
        unit="count",
        direction=direction,
        definition=definition,
    )


def _fraction(
    identifier: str,
    label: str,
    numerator: Any,
    denominator: Any,
    definition: str,
    *,
    direction="higher",
):
    count = _int(numerator, f"{identifier}.count")
    total = _int(denominator, f"{identifier}.total")
    if total < 1 or count > total:
        raise ValueError(f"Invalid {identifier} fraction")
    return LabMetric(
        id=identifier,
        label=label,
        value=round(count * 100 / total, 1),
        unit="percent",
        numerator=count,
        denominator=total,
        direction=direction,
        definition=definition,
    )


def _recorded_fraction(identifier: str, label: str, value: Any, definition: str, *, direction="higher"):
    record = _dict(value, identifier)
    return _fraction(
        identifier,
        label,
        record.get("count"),
        record.get("total"),
        definition,
        direction=direction,
    )


def _seconds(identifier: str, label: str, value: Any, definition: str):
    number = _float(value, identifier)
    return LabMetric(
        id=identifier,
        label=label,
        value=round(number, 3),
        unit="seconds",
        direction="lower",
        definition=definition,
    )


def _text(identifier: str, label: str, value: bool, definition: str):
    return LabMetric(
        id=identifier,
        label=label,
        value="Yes" if _bool(value, identifier) else "No",
        unit="text",
        direction="neutral",
        definition=definition,
    )


def _suite(
    definition: SuiteSpec,
    metrics: list[LabMetric],
    limitations: list[str],
    *,
    status="informational",
    recorded_at=None,
):
    return LabSuite(
        id=definition.id,
        title=definition.title,
        feature=definition.feature,
        category=definition.category,
        status=status,
        gated=definition.gated,
        recorded_at=recorded_at,
        metrics=metrics,
        source_label=definition.relative_path,
        limitations=limitations,
        warnings=[],
    )


def parse_search(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    split = "holdout" if definition.category == "held_out" else "dev"
    summary = _dict(_dict(data.get("summary"), "summary").get(split), split)
    metrics = [
        _count("cases", "Cases", summary.get("cases"), "Labelled cases in this partition."),
        _fraction(
            "suggestion_top3_hits",
            "Suggestion hit rate",
            summary.get("suggestion_top3_hits"),
            summary.get("typo_cases"),
            "Misspelled queries whose labelled result appeared in the first three suggestions.",
        ),
        _count(
            "negative_false_suggestions",
            "False negative-query suggestions",
            summary.get("negative_false_suggestions"),
            "Unwanted suggestions returned for queries labelled as unrelated.",
            direction="lower",
        ),
        _count(
            "exact_unwanted_suggestions",
            "Unwanted exact-query suggestions",
            summary.get("exact_unwanted_suggestions"),
            "Suggestion prompts incorrectly shown for already exact queries.",
            direction="lower",
        ),
    ]
    return _suite(
        definition,
        metrics,
        _limitations(data.get("scope"), "Small labelled search evaluation."),
    )


def parse_content_quality(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    if data.get("partition") != "held-out" or data.get("state") != "complete":
        raise ValueError("Unsupported content-quality report")
    metrics = _dict(data.get("metrics"), "metrics")
    values = [
        _recorded_fraction("label_matches", "Label agreement", metrics.get("label_matches"), "Decisions matching the frozen expected label."),
        _recorded_fraction("useful_acceptance", "Useful acceptance", metrics.get("useful_acceptance"), "Supported useful items accepted by the critic."),
        _recorded_fraction("false_acceptance", "False acceptance", metrics.get("false_acceptance"), "Items expected to be rejected but accepted.", direction="lower"),
        _recorded_fraction("false_rejection", "False rejection", metrics.get("false_rejection"), "Items expected to be accepted but rejected.", direction="lower"),
        _recorded_fraction("uncertain", "Uncertain decisions", metrics.get("uncertain"), "Cases assigned an uncertain decision.", direction="lower"),
        _recorded_fraction("errors", "Evaluation errors", metrics.get("errors"), "Cases that did not produce a valid evaluation decision.", direction="lower"),
    ]
    return _suite(
        definition,
        values,
        _limitations(data.get("limitations"), "Held-out synthetic critic evaluation."),
    )


def parse_fact_inspection(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    if data.get("state") != "complete":
        raise ValueError("Unsupported fact inspection")
    items = _list(data.get("inspected_items"), "inspected_items")
    generation = _dict(data.get("final_generation"), "final_generation")
    values = [
        _fraction(
            "inspection_supported",
            "Inspection-supported drafts",
            data.get("inspection_supported_count"),
            len(items),
            "Generated drafts judged supported during the recorded assistant inspection.",
        ),
        _count("proposed_facts", "Proposed facts", generation.get("proposed_facts"), "Facts produced in the final generation run."),
        _count("eligible_drafts", "Automatically eligible drafts", generation.get("eligible_drafts"), "Drafts retained by the automated eligibility checks."),
        _count("generation_errors", "Generation errors", generation.get("error_movies"), "Movies whose final generation failed.", direction="lower"),
        _seconds("generation_seconds", "Generation time", data.get("generation_seconds"), "Recorded elapsed time for the final generation run."),
        _text("publication_performed", "Publication performed", data.get("publication_performed"), "Whether this inspection changed consumer content."),
    ]
    return _suite(
        definition,
        values,
        _limitations(data.get("limitations"), "Assistant-inspected development evidence."),
    )


def parse_quiz_completion(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    if data.get("policy") != "quiz-replacement-completion-final-v1" or data.get("status") != "proposal_only":
        raise ValueError("Unsupported quiz completion report")
    summary = _dict(data.get("summary"), "summary")
    metrics = _dict(data.get("metrics"), "metrics")
    recovery = _dict(metrics.get("evidence_recovery"), "evidence_recovery")
    generation = _dict(metrics.get("generation"), "generation")
    editorial = _dict(metrics.get("editorial"), "editorial")
    completion = _dict(_dict(metrics.get("whole_bank"), "whole_bank").get("completion"), "completion")
    values = [
        _fraction("ready", "Ready replacements", summary.get("ready"), summary.get("targets"), "Targets ready for final selection after all recorded reviews."),
        _count("withheld", "Withheld replacements", summary.get("withheld"), "Targets deliberately withheld from publication."),
        _fraction("evidence_accepted", "Evidence accepted", recovery.get("accepted"), recovery.get("targets"), "Targets whose broader evidence passed source inspection."),
        _fraction("deterministic_passes", "Deterministic passes", generation.get("deterministic_passes"), generation.get("targets"), "Targets passing exact answer, citation, wording, and option checks."),
        _fraction("critic_accepts", "Critic accepts", generation.get("critic_accepts"), generation.get("targets"), "Targets accepted by the structured critic after deterministic checks."),
        _fraction("editorial_accepts", "Editorial accepts", editorial.get("editorial_accepts"), editorial.get("targets"), "Targets accepted during the recorded editorial inspection."),
        _count("completion_errors", "Completion review errors", completion.get("errors"), "Whole-bank completion reviews that failed.", direction="lower"),
        _seconds("recorded_model_seconds", "Recorded model time", metrics.get("recorded_model_seconds"), "Sum of recorded local-model durations for this workflow."),
    ]
    return _suite(
        definition,
        values,
        ["Proposal-only workflow; ready items were not automatically published."],
        recorded_at=_timestamp(data.get("generated_at")),
    )


def parse_discussion_retrieval(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    candidate = _dict(_dict(data.get("metrics"), "metrics").get("candidate"), "candidate")
    baseline = _dict(_dict(data.get("metrics"), "metrics").get("baseline"), "baseline")
    values = [
        _fraction("candidate_passed", "Candidate checks passed", candidate.get("automated_passed"), candidate.get("total"), "Automated development checks passed by the candidate retrieval path."),
        _fraction("baseline_passed", "Baseline checks passed", baseline.get("automated_passed"), baseline.get("total"), "The same checks passed by the frozen baseline."),
        _fraction("supporting_hit_at_3", "Supporting hit at 3", candidate.get("annotated_supporting_hit_at_3"), candidate.get("answerable_cases"), "Answerable cases with an annotated supporting passage among the first three hits."),
        _fraction("expected_abstentions", "Expected abstentions", candidate.get("expected_abstentions_passed"), candidate.get("expected_abstentions"), "Missing-evidence cases that correctly abstained."),
        _count("generation_errors", "Generation errors", candidate.get("generation_errors"), "Candidate cases that failed to generate a valid answer.", direction="lower"),
        _seconds("median_seconds", "Observed median time", candidate.get("observed_median_seconds"), "Recorded warm sequential end-to-end median, not isolated retrieval latency."),
    ]
    return _suite(
        definition,
        values,
        _limitations(data.get("limitations"), "Consumed discussion development cases."),
        recorded_at=_timestamp(data.get("created_at_utc")),
    )


def parse_discussion_support(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    if data.get("policy") != "discussion-support-review-v6":
        raise ValueError("Unsupported discussion support report")
    summary = _dict(data.get("summary"), "summary")
    values = [
        _fraction("passed", "Support controls passed", summary.get("passed"), summary.get("total"), "Authored support-review controls matching their expected verdict."),
        _count("false_acceptances", "False acceptances", summary.get("false_acceptances"), "Unsupported answers incorrectly accepted by the reviewer.", direction="lower"),
        _count("false_rejections", "False rejections", summary.get("false_rejections"), "Supported answers incorrectly rejected by the reviewer.", direction="lower"),
    ]
    return _suite(
        definition,
        values,
        _limitations(data.get("limitations"), "Consumed discussion support controls."),
        recorded_at=_timestamp(data.get("created_at_utc")),
    )


def parse_multi_source_smoke(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    cases = _list(data.get("cases"), "cases")
    checks = _dict(data.get("checks"), "checks")
    passed = sum(_bool(value, f"checks.{key}") for key, value in checks.items())
    degraded = 0
    for case in cases:
        coverage = _dict(_dict(case, "case").get("coverage"), "coverage")
        degraded += int(_bool(coverage.get("degraded"), "coverage.degraded"))
    values = [
        _count("cases", "Smoke cases", len(cases), "Consumed local-model smoke cases."),
        _fraction("checks_passed", "Smoke checks passed", passed, len(checks), "Code-owned smoke expectations satisfied by the recorded cases."),
        _count("degraded_cases", "Degraded cases", degraded, "Cases whose source acquisition reported reduced coverage.", direction="lower"),
        _text("banks_unchanged", "Published banks unchanged", data.get("published_banks_unchanged"), "Whether the smoke run left shared published content unchanged."),
    ]
    return _suite(
        definition,
        values,
        _limitations(data.get("scope"), "Development smoke only."),
        recorded_at=_timestamp(data.get("run_date")),
    )


def parse_readiness(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    summary = _dict(data.get("summary"), "summary")
    passed = _int(summary.get("passed"), "summary.passed")
    total = _int(summary.get("total"), "summary.total")
    status = "pass" if definition.gated and total > 0 and passed == total else (
        "attention" if definition.gated else "informational"
    )
    values = [_fraction("passed", "Readiness controls passed", passed, total, "Recorded readiness controls matching their expected decision.")]
    if "seconds" in data:
        values.append(_seconds("seconds", "Recorded run time", data.get("seconds"), "Elapsed time recorded by the readiness replay."))
    return _suite(
        definition,
        values,
        _limitations(data.get("limitations"), "Development readiness controls."),
        status=status,
    )


def parse_twenty_film_audit(data: dict[str, Any], definition: SuiteSpec) -> LabSuite:
    jobs = _bool(data.get("all_jobs_reviewable"), "all_jobs_reviewable")
    selections = _bool(data.get("all_selections_compile"), "all_selections_compile")
    values = [
        _count("movie_count", "Movies audited", data.get("movie_count"), "Movie banks included in the reviewability audit."),
        _text("jobs_reviewable", "Jobs reviewable", jobs, "Whether every audited preparation job was reviewable."),
        _text("selections_compile", "Selections compile", selections, "Whether every reviewed selection compiled against its frozen report."),
    ]
    return _suite(
        definition,
        values,
        ["Integrity and reviewability audit; not claim-level semantic accuracy."],
        status="pass" if definition.gated and jobs and selections else "attention",
        recorded_at=_timestamp(data.get("generated_at")),
    )
