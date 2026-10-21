"""Shared narrative-quality labels, evaluation metrics, and advisory surface flags."""
import re
from typing import Literal

from pydantic import Field, model_validator

from .content_proposals import StrictRecord

NarrativeFocus = Literal[
    "turning_point", "choice_or_motivation", "cause_or_consequence",
    "relationship", "theme_or_concept", "ending_or_resolution", "story_rule",
    "granular_recall", "not_applicable",
]
NarrativeSignificance = Literal["central", "supporting", "granular", "not_applicable"]

QUIZ_FOCI = (
    "turning_point", "choice_or_motivation", "cause_or_consequence",
    "relationship", "theme_or_concept", "ending_or_resolution", "story_rule",
    "granular_recall",
)
QUIZ_SIGNIFICANCE = ("central", "supporting", "granular")
MEANINGFUL_FOCI = frozenset(QUIZ_FOCI) - {"granular_recall"}


def narrative_eligible(focus: str, significance: str) -> bool:
    """Code owns acceptance after a critic supplies bounded semantic labels."""
    if focus not in (*QUIZ_FOCI, "not_applicable"):
        raise ValueError("Unknown narrative focus")
    if significance not in (*QUIZ_SIGNIFICANCE, "not_applicable"):
        raise ValueError("Unknown narrative significance")
    return focus in MEANINGFUL_FOCI and significance in {"central", "supporting"}


def narrative_surface_blocks(question: str) -> list[str]:
    """Return narrow code-owned vetoes for isolated recall stems."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A question is required")
    identity = re.compile(
        r"^(?:who\b|(?:which|what)\s+(?:(?:recruited\s+)?team|crew|cast)\s+member\b)",
        re.I,
    )
    action = re.compile(
        r"^(?:what action does\b|what does\s+.{1,80}\s+do\s+(?:with|regarding|to|about)\b)",
        re.I,
    )
    blocks = []
    if identity.search(question.strip()):
        blocks.append("isolated_identity_recall")
    if action.search(question.strip()):
        blocks.append("isolated_action_recall")
    return blocks


class NarrativeCase(StrictRecord):
    id: str = Field(pattern=r"^NQ[0-9]{3}$")
    movie: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=10, max_length=300)
    expected_focus: NarrativeFocus
    expected_significance: NarrativeSignificance
    expected_eligible: bool

    @model_validator(mode="after")
    def coherent_label(self):
        if self.expected_eligible != narrative_eligible(
            self.expected_focus, self.expected_significance
        ):
            raise ValueError("Eligibility must follow the code-owned narrative policy")
        return self


class NarrativeDataset(StrictRecord):
    policy: Literal["plotspot-narrative-quiz-eval-v1"]
    partition: Literal["development"]
    cases: list[NarrativeCase] = Field(min_length=20, max_length=100)

    @model_validator(mode="after")
    def unique_balanced_cases(self):
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Narrative case IDs must be unique")
        positives = sum(case.expected_eligible for case in self.cases)
        if positives < 10 or len(self.cases) - positives < 10:
            raise ValueError("Narrative development cases must include both classes")
        return self


class NarrativePrediction(StrictRecord):
    id: str = Field(pattern=r"^NQ[0-9]{3}$")
    focus: NarrativeFocus
    significance: NarrativeSignificance


class NarrativePredictions(StrictRecord):
    items: list[NarrativePrediction] = Field(min_length=1, max_length=100)


def score_predictions(dataset: NarrativeDataset, predictions: list[NarrativePrediction]) -> dict:
    by_id = {prediction.id: prediction for prediction in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case.id for case in dataset.cases}:
        raise ValueError("Provide exactly one prediction for every narrative case")
    rows = []
    for case in dataset.cases:
        prediction = by_id[case.id]
        predicted_eligible = narrative_eligible(prediction.focus, prediction.significance)
        rows.append({
            "id": case.id,
            "expected_eligible": case.expected_eligible,
            "predicted_eligible": predicted_eligible,
            "focus_match": prediction.focus == case.expected_focus,
            "significance_match": prediction.significance == case.expected_significance,
        })
    positives = [row for row in rows if row["expected_eligible"]]
    negatives = [row for row in rows if not row["expected_eligible"]]
    retained = sum(row["predicted_eligible"] for row in positives)
    rejected = sum(not row["predicted_eligible"] for row in negatives)
    correct = sum(row["expected_eligible"] == row["predicted_eligible"] for row in rows)
    return {
        "policy": dataset.policy,
        "partition": dataset.partition,
        "cases": len(rows),
        "metrics": {
            "useful_retention_percent": round(100 * retained / len(positives), 1),
            "granular_rejection_percent": round(100 * rejected / len(negatives), 1),
            "eligibility_accuracy_percent": round(100 * correct / len(rows), 1),
            "focus_accuracy_percent": round(100 * sum(row["focus_match"] for row in rows) / len(rows), 1),
            "significance_accuracy_percent": round(100 * sum(row["significance_match"] for row in rows) / len(rows), 1),
        },
        "rows": rows,
        "limitations": [
            "These are authored development labels, not an independent held-out benchmark.",
            "Narrative value can depend on context that is absent from a question stem.",
        ],
    }


_SURFACE_RULES = (
    ("exact_count_or_duration", re.compile(r"^how many\b|\bhow (?:long|old)\b", re.I)),
    ("isolated_name", re.compile(r"^(?:what is the name of|who is|who was|who visits)\b", re.I)),
    ("isolated_location", re.compile(r"^(?:where|in which (?:city|country|location))\b", re.I)),
    ("isolated_object", re.compile(r"^(?:what|which) (?:object|item|vehicle|robot|weapon|painting|pill|planet)\b", re.I)),
)


def advisory_surface_flags(question: str) -> list[str]:
    """Flag likely recall questions for review; never decide deletion or publication."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A question is required")
    return [name for name, pattern in _SURFACE_RULES if pattern.search(question.strip())]
