"""Deterministic aggregation for the read-only AI reliability lab."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .lab_contracts import (
    FeatureHealth,
    LabOverview,
    LabRunList,
    LabSuite,
    PipelineStageHealth,
)
from .lab_registry import load_evaluation_suites


SUCCESSFUL_RUNS = {"completed", "needs_review", "ready", "published"}
FAILED_RUNS = {"failed", "cancelled", "interrupted", "incomplete"}
STAGE_SUITES = {
    "search": {
        "retrieval": ("search_development", "search_held_out"),
        "generation": None,
        "verification": None,
        "publication": None,
    },
    "facts": {
        "retrieval": ("multi_source_smoke",),
        "generation": ("fact_inspection",),
        "verification": ("fact_inspection", "content_quality_held_out"),
        "publication": ("twenty_film_audit",),
    },
    "quiz": {
        "retrieval": ("multi_source_smoke",),
        "generation": ("quiz_replacement_completion",),
        "verification": ("quiz_replacement_completion", "content_quality_held_out"),
        "publication": ("twenty_film_audit",),
    },
    "discuss": {
        "retrieval": ("discussion_retrieval",),
        "generation": ("multi_source_smoke",),
        "verification": ("discussion_support",),
        "publication": None,
    },
}


class LabService:
    def __init__(
        self,
        project_root: Path,
        runs,
        *,
        suite_loader: Callable[[Path], tuple[list[LabSuite], list]] = load_evaluation_suites,
        clock: Callable[[], datetime] | None = None,
    ):
        self.project_root = Path(project_root)
        self.runs = runs
        self.suite_loader = suite_loader
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def overview(self) -> LabOverview:
        suites, suite_warnings = self.suite_loader(self.project_root)
        runs, run_warnings = self.runs.list(None, None, 20)
        warnings = (suite_warnings + run_warnings)[:20]
        gated = [suite for suite in suites if suite.gated]
        gated_passed = sum(suite.status == "pass" for suite in gated)
        held_out_passed, held_out_total = self._held_out_cases(suites)
        recent_successful = sum(run.state in SUCCESSFUL_RUNS and not run.degraded for run in runs)
        degraded_or_failed = sum(run.degraded or run.state in FAILED_RUNS for run in runs)
        readable = any(suite.status not in {"error", "no_data"} for suite in suites)
        gated_attention = any(suite.status in {"attention", "error"} for suite in gated)
        if gated_attention or degraded_or_failed:
            status = "attention"
        elif not readable and not runs:
            status = "no_data"
        elif warnings:
            status = "partial"
        elif gated and gated_passed == len(gated):
            status = "healthy"
        else:
            status = "partial"
        return LabOverview(
            generated_at=self.clock(),
            status=status,
            gated_passed=gated_passed,
            gated_total=len(gated),
            held_out_passed=held_out_passed,
            held_out_total=held_out_total,
            recent_successful_runs=recent_successful,
            degraded_or_failed_runs=degraded_or_failed,
            suites=suites,
            features=self._feature_health(suites),
            warnings=warnings,
            limitations=[
                "Development, held-out, smoke, publication, and audit evidence retain separate meanings.",
                "Informational reports are excluded from gated pass-rate denominators.",
                "Recent runs are bounded local records, not a complete event history or production monitor.",
                "Automated checks and assistant review do not establish general model accuracy or safety.",
            ],
        )

    def list_runs(self, workflow, state, limit) -> LabRunList:
        items, warnings = self.runs.list(workflow, state, limit)
        return LabRunList(items=items, warnings=warnings)

    def get_run(self, run_id):
        return self.runs.get(run_id)

    @staticmethod
    def _held_out_cases(suites):
        selected = {
            "search_held_out": "suggestion_top3_hits",
            "content_quality_held_out": "label_matches",
        }
        passed = total = 0
        for suite in suites:
            metric_id = selected.get(suite.id)
            if not metric_id:
                continue
            metric = next((item for item in suite.metrics if item.id == metric_id), None)
            if metric and metric.numerator is not None and metric.denominator is not None:
                passed += metric.numerator
                total += metric.denominator
        return passed, total

    @staticmethod
    def _feature_health(suites):
        by_id = {suite.id: suite for suite in suites}
        features = []
        for feature, definitions in STAGE_SUITES.items():
            stages = []
            for stage, identifiers in definitions.items():
                if identifiers is None:
                    stages.append(PipelineStageHealth(
                        stage=stage,
                        status="not_applicable",
                        detail="This stage does not apply to the feature.",
                    ))
                    continue
                related = [by_id[item] for item in identifiers if item in by_id]
                if any(item.status in {"attention", "error"} for item in related):
                    state, detail = "attention", "A registered gate or report needs attention."
                elif any(item.status == "pass" for item in related):
                    state, detail = "healthy", "The registered gate passed."
                elif related and any(item.status == "informational" for item in related):
                    state, detail = "no_data", "Measurements exist without a pass/fail gate."
                else:
                    state, detail = "no_data", "No valid registered evidence is available."
                stages.append(PipelineStageHealth(stage=stage, status=state, detail=detail))
            applicable = [stage for stage in stages if stage.status != "not_applicable"]
            if any(stage.status == "attention" for stage in applicable):
                feature_status = "attention"
            elif applicable and all(stage.status == "healthy" for stage in applicable):
                feature_status = "healthy"
            elif any(stage.status == "healthy" for stage in applicable):
                feature_status = "partial"
            else:
                feature_status = "no_data"
            features.append(FeatureHealth(feature=feature, status=feature_status, stages=stages))
        return features
