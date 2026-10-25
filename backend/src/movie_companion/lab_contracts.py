"""Strict, sanitized contracts for the local developer reliability lab."""

from datetime import datetime
from typing import Literal

from pydantic import Field, FiniteFloat, StrictInt, model_validator

from .content_proposals import StrictRecord


EvidenceCategory = Literal[
    "development", "held_out", "smoke", "live", "publication", "audit"
]
SuiteStatus = Literal["pass", "attention", "informational", "error", "no_data"]
RunState = Literal[
    "queued",
    "running",
    "completed",
    "needs_review",
    "incomplete",
    "ready",
    "published",
    "failed",
    "cancelled",
    "interrupted",
]
Feature = Literal["search", "facts", "quiz", "discuss", "retrieval", "readiness"]


class LabMetric(StrictRecord):
    id: str = Field(pattern=r"^[a-z0-9_]{1,50}$")
    label: str = Field(min_length=1, max_length=100)
    value: StrictInt | FiniteFloat | str
    unit: Literal["count", "percent", "seconds", "ratio", "text"]
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=1)
    direction: Literal["higher", "lower", "neutral"] = "neutral"
    definition: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def percentage_has_fraction(self):
        if self.unit == "percent" and (
            self.numerator is None or self.denominator is None
        ):
            raise ValueError("Percent metrics require numerator and denominator")
        return self


class LabWarning(StrictRecord):
    code: Literal["missing_source", "invalid_source", "unsupported_source"]
    suite_id: str | None = Field(default=None, max_length=60)
    message: str = Field(min_length=1, max_length=240)


class LabSuite(StrictRecord):
    id: str = Field(pattern=r"^[a-z0-9_]{1,60}$")
    title: str = Field(min_length=1, max_length=120)
    feature: Feature
    category: EvidenceCategory
    status: SuiteStatus
    gated: bool
    recorded_at: datetime | None = None
    metrics: list[LabMetric] = Field(max_length=30)
    source_label: str = Field(min_length=1, max_length=160)
    limitations: list[str] = Field(max_length=12)
    warnings: list[LabWarning] = Field(max_length=12)


class PipelineStageHealth(StrictRecord):
    stage: Literal["retrieval", "generation", "verification", "publication"]
    status: Literal["healthy", "attention", "no_data", "not_applicable"]
    detail: str = Field(min_length=1, max_length=180)


class FeatureHealth(StrictRecord):
    feature: Literal["search", "facts", "quiz", "discuss"]
    status: Literal["healthy", "attention", "partial", "no_data"]
    stages: list[PipelineStageHealth] = Field(min_length=1, max_length=4)


class LabOverview(StrictRecord):
    generated_at: datetime
    status: Literal["healthy", "attention", "partial", "no_data"]
    gated_passed: int = Field(ge=0)
    gated_total: int = Field(ge=0)
    held_out_passed: int = Field(ge=0)
    held_out_total: int = Field(ge=0)
    recent_successful_runs: int = Field(ge=0)
    degraded_or_failed_runs: int = Field(ge=0)
    suites: list[LabSuite] = Field(max_length=20)
    features: list[FeatureHealth] = Field(max_length=4)
    warnings: list[LabWarning] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)


class LabRunStage(StrictRecord):
    name: Literal[
        "source",
        "index",
        "retrieve",
        "retrieving",
        "generate",
        "generating",
        "verify",
        "reviewing",
        "finished",
    ]
    status: Literal["completed", "running", "attention", "pending", "unavailable"]
    duration_seconds: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    count: int | None = Field(default=None, ge=0)
    message: str = Field(min_length=1, max_length=180)


class LabRunSummary(StrictRecord):
    id: str = Field(pattern=r"^(?:prep|story)_[a-f0-9]{32}$")
    movie_id: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=200)
    workflow: Literal["preparation", "story_rag"]
    state: RunState
    updated_at: datetime
    duration_seconds: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    source_count: int = Field(ge=0)
    retrieval_count: int = Field(ge=0)
    degraded: bool
    warnings: list[LabWarning] = Field(max_length=10)


class LabRunDetail(LabRunSummary):
    stages: list[LabRunStage] = Field(min_length=1, max_length=12)


class LabRunList(StrictRecord):
    items: list[LabRunSummary] = Field(max_length=50)
    warnings: list[LabWarning] = Field(max_length=20)
