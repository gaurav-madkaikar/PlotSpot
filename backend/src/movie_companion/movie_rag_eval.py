"""Human-labelled development checks; automated matches are not entailment."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .grounding_learning import GroundedAnswer
from .retrieval_learning import RetrievalHit


class MovieRagCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    question: str = Field(min_length=1, max_length=1000)
    expected_status: Literal["answered", "insufficient_evidence"]
    relevant_passage_ids: list[str] = Field(max_length=200)
    required_phrase_groups: list[list[str]] = Field(max_length=10)

    @model_validator(mode="after")
    def valid_labels(self):
        if not self.question.strip():
            raise ValueError("Question must not be blank")
        if len(set(self.relevant_passage_ids)) != len(self.relevant_passage_ids):
            raise ValueError("Supporting IDs must be unique")
        if any(not identifier or len(identifier) > 64 for identifier in self.relevant_passage_ids):
            raise ValueError("Invalid supporting ID")
        if self.expected_status == "answered" and (not self.relevant_passage_ids or not self.required_phrase_groups):
            raise ValueError("Answerable cases need supporting IDs and expected phrases")
        if self.expected_status == "insufficient_evidence" and (self.relevant_passage_ids or self.required_phrase_groups):
            raise ValueError("Missing-evidence cases have no supporting IDs or expected facts")
        if any(not group or len(group) > 10 or any(not phrase.strip() or len(phrase) > 200 for phrase in group) for group in self.required_phrase_groups):
            raise ValueError("Phrase groups require bounded, nonblank alternatives")
        return self


class MovieRagDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: str = Field(min_length=1, max_length=100)
    split: Literal["development"]
    source_snapshot: str = Field(pattern=r"^[a-f0-9]{64}$")
    cases: list[MovieRagCase] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_cases(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique")
        return self


def validate_snapshot(dataset: MovieRagDataset, snapshot: str, passage_ids: set[str]) -> None:
    if dataset.source_snapshot != snapshot:
        raise ValueError("Source snapshot changed; review labels before evaluating")
    for case in dataset.cases:
        if not set(case.relevant_passage_ids) <= passage_ids:
            raise ValueError(f"Unknown supporting passage ID in {case.id}")


def grade_case(case: MovieRagCase, hits: list[RetrievalHit], answer: GroundedAnswer | None, *, allowed_citation_ids=None) -> dict:
    retrieved = {hit.passage.passage_id for hit in hits}
    relevant = set(case.relevant_passage_ids)
    failures = []
    if relevant and not retrieved & relevant:
        failures.append("No labelled supporting passage retrieved")
    if answer is None:
        failures.append("Generation or response validation failed")
    else:
        if answer.status != case.expected_status:
            failures.append("Answer status differs from expectation")
        if not set(answer.citation_ids) <= (retrieved if allowed_citation_ids is None else set(allowed_citation_ids)):
            failures.append("Citation outside retrieved evidence")
        if answer.status == "answered" and not answer.citation_ids:
            failures.append("Answered without a citation")
        if answer.status == "insufficient_evidence" and answer.citation_ids:
            failures.append("Abstention must not cite evidence")
        if case.expected_status == "answered" and not set(answer.citation_ids) & relevant:
            failures.append("No labelled supporting passage cited")
        text = answer.answer.casefold()
        for group in case.required_phrase_groups:
            if not any(phrase.casefold() in text for phrase in group):
                failures.append(f"Missing expected phrase group: {group}")
    return {
        "supporting_hit_at_3": bool(retrieved & relevant) if relevant else None,
        "annotated_id_recall_at_3": len(retrieved & relevant) / len(relevant) if relevant else None,
        "automated_pass": not failures, "failures": failures,
        "human_claim_support_review": "pending",
    }
