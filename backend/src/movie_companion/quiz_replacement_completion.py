"""Frozen scope and reviewed intent contracts for quiz replacement completion."""

from collections import Counter
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import Field, model_validator

from .content_proposals import StrictRecord
from .quiz_replacement_workflow import build_targets
from .research_checkpoint import digest


POLICY = "quiz-replacement-completion-manifest-v1"
CONTRACT_POLICY = "quiz-replacement-intent-contracts-v1"
Lane = Literal["intent", "evidence", "novelty"]
Relation = Literal[
    "motivation",
    "consequence",
    "relationship",
    "role",
    "choice",
    "theme",
    "ending",
    "story_rule",
]
AnswerShape = Literal[
    "reason",
    "outcome",
    "role",
    "relationship",
    "action",
    "state_change",
    "idea",
]

SHAPE_PATTERNS = {
    "reason": (
        r"^why\b",
        r"\bwhat (?:reason|motivates?|motivation|purpose)\b",
    ),
    "outcome": (
        r"\b(?:consequence|result|effect)\b",
        r"\bwhat happens\b",
        r"\bhow does .+ (?:affect|change|alter|threaten|expose|redirect|help)\b",
        r"\bwhat does .+ (?:cause|lead to|change|make possible)\b",
        r"\bwhat follows\b",
    ),
    "role": (
        r"\b(?:role|function|purpose)\b",
        r"\bhow does .+ (?:help|enable|allow|serve|carry|rescue|support)\b",
        r"\bwhat does .+ (?:make possible|provide|enable|allow)\b",
        r"\bwhy is .+ important\b",
    ),
    "relationship": (
        r"\brelationship\b",
        r"\bwhat changes between\b",
        r"\bhow (?:are|is) .+ connected\b",
        r"\bwho(?:m)? does .+ reconnect\b",
        r"\bwhat does .+ learn about .+ (?:father|mother|son|daughter|parent)\b",
    ),
    "action": (
        r"^what does\b",
        r"^how does\b",
        r"\bwhich (?:choice|action|decision)\b",
    ),
    "state_change": (
        r"\bhow does .+ change\b",
        r"\bwhat changes\b",
        r"\bwhat becomes\b",
        r"\bwhat does .+ (?:discover|learn|realize)\b",
        r"\bwhat is revealed\b",
    ),
    "idea": (
        r"\bwhat idea\b",
        r"\bwhich theme\b",
        r"\bwhat does .+ (?:show|suggest|represent|mean)\b",
        r"\bcentral conflict\b",
        r"\bwhat drives\b",
        r"\bwhat do .+ (?:fight|battle|struggle)\b",
    ),
}


class NarrativeIntent(StrictRecord):
    question_id: str = Field(min_length=1, max_length=200)
    focus: str = Field(min_length=3, max_length=240)
    relation: Relation
    required_concepts: list[list[str]] = Field(min_length=1, max_length=6)
    forbidden_details: list[str] = Field(default_factory=list, max_length=8)
    expected_answer_shape: AnswerShape
    difficulty: Literal["general_viewer"] = "general_viewer"

    @model_validator(mode="after")
    def bounded_aliases(self):
        if any(not 1 <= len(group) <= 5 for group in self.required_concepts):
            raise ValueError("Each required concept needs one to five aliases")
        for group in self.required_concepts:
            if any(
                not isinstance(value, str) or not 1 <= len(value.strip()) <= 80
                for value in group
            ):
                raise ValueError("Invalid required concept alias")
            normalized = [" ".join(value.casefold().split()) for value in group]
            if len(normalized) != len(set(normalized)):
                raise ValueError("Duplicate required concept alias")
        if any(
            not isinstance(value, str) or not 1 <= len(value.strip()) <= 80
            for value in self.forbidden_details
        ):
            raise ValueError("Invalid forbidden detail")
        return self


class CompletionTarget(StrictRecord):
    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    question_id: str = Field(min_length=1, max_length=200)
    old_question: str = Field(min_length=1, max_length=250)
    old_answer: str = Field(min_length=1, max_length=150)
    replacement_brief: str = Field(min_length=10, max_length=500)
    bank_version: str = Field(min_length=1, max_length=120)
    bank_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lane: Lane
    originating_artifacts: dict[str, str] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def valid_artifact_hashes(self):
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for name, value in self.originating_artifacts.items()
        ):
            raise ValueError("Invalid originating artifact hash")
        return self


class CompletionManifest(StrictRecord):
    policy: Literal["quiz-replacement-completion-manifest-v1"]
    source_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    whole_bank_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[CompletionTarget] = Field(min_length=31, max_length=31)

    @model_validator(mode="after")
    def exact_scope(self):
        identities = [(item.movie_id, item.question_id) for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate completion target")
        counts = Counter(item.lane for item in self.items)
        if counts != Counter(intent=13, evidence=17, novelty=1):
            raise ValueError("Unexpected completion lane counts")
        return self

    @property
    def summary(self):
        counts = Counter(item.lane for item in self.items)
        return {
            "unresolved": len(self.items),
            "intent": counts["intent"],
            "evidence": counts["evidence"],
            "novelty": counts["novelty"],
        }


def _normal(value: str):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _stem(token: str):
    """Normalize a few safe English inflections without semantic expansion."""
    for suffix in (
        "ations", "ation", "ments", "ment", "ables", "able", "ibles", "ible",
        "ings", "ing", "ied", "ies", "ed", "es", "s", "ry",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            replacement = "y" if suffix in ("ied", "ies") else ""
            return token[:-len(suffix)] + replacement
    return token


def _contains_concept(text: str, alias: str):
    """Match reviewed aliases as an ordered, inflection-normalized token sequence."""
    haystack = [_stem(token) for token in _normal(text).split()]
    needle = [_stem(token) for token in _normal(alias).split()]
    if not needle:
        return False
    position = 0
    for token in haystack:
        if token == needle[position]:
            position += 1
            if position == len(needle):
                return True
    return False


def intent_contract_problems(question: str, answer: str, *, intent: NarrativeIntent):
    """Check reviewed concepts and question form without inferring movie facts."""
    if not isinstance(question, str) or not isinstance(answer, str):
        raise ValueError("Question and answer must be text")
    combined = _normal(f"{question} {answer}")
    problems = []
    if any(
        not any(_contains_concept(combined, alias) for alias in group)
        for group in intent.required_concepts
    ):
        problems.append("missing_required_concept")
    if any(_normal(detail) in combined for detail in intent.forbidden_details):
        problems.append("forbidden_detail")
    if not any(
        re.search(pattern, question.casefold())
        for pattern in SHAPE_PATTERNS[intent.expected_answer_shape]
    ):
        problems.append("answer_shape_mismatch")
    return problems


def load_completion_manifest(path: Path):
    payload = json.loads(Path(path).read_text())
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "proposal_only"
        or payload.get("published") is not False
        or payload.get("publication")
        != {"authorized": False, "database_mutated": False}
    ):
        raise ValueError("Expected proposal-only completion manifest")
    fields = set(CompletionManifest.model_fields)
    manifest = CompletionManifest.model_validate(
        {key: value for key, value in payload.items() if key in fields}
    )
    if payload.get("summary") != manifest.summary:
        raise ValueError("Completion manifest summary changed")
    return manifest


def _proposal_input(value, *, policy, name):
    if (
        not isinstance(value, dict)
        or value.get("policy") != policy
        or value.get("status") != "proposal_only"
        or value.get("published", False) is not False
    ):
        raise ValueError(f"Expected proposal-only {name}")
    return value


def _bank_sha256(saved):
    return digest(saved["quiz"].model_dump(mode="json"))


def build_completion_manifest(source_review, evidence_review, whole_bank_review, bank):
    """Derive the unresolved lanes from pinned review state, never title rules."""
    _proposal_input(
        source_review,
        policy="assistant-semantic-quiz-bank-review-v1",
        name="saved-bank review",
    )
    _proposal_input(
        evidence_review,
        policy="assistant-replacement-evidence-editorial-v1",
        name="replacement-evidence review",
    )
    if (
        not isinstance(whole_bank_review, dict)
        or whole_bank_review.get("policy")
        != "provisional-whole-bank-novelty-review-v1"
        or whole_bank_review.get("published") is not False
    ):
        raise ValueError("Expected proposal-only whole-bank review")

    source_sha = digest(source_review)
    evidence_sha = digest(evidence_review)
    whole_bank_sha = digest(whole_bank_review)
    decisions = {
        (item["movie_id"], item["question_id"]): item
        for item in source_review.get("decisions", [])
        if isinstance(item, dict) and item.get("disposition") == "replace"
    }
    if len(decisions) != 34:
        raise ValueError("Expected thirty-four original replacement decisions")

    evidence = {}
    for item in evidence_review.get("items", []):
        identity = (item.get("movie_id"), item.get("question_id"))
        if identity in evidence:
            raise ValueError("Duplicate replacement-evidence decision")
        decision = item.get("editorial_decision")
        if decision not in ("accept", "reject"):
            raise ValueError("Invalid replacement-evidence decision")
        evidence[identity] = decision

    ready = set()
    novelty = set()
    for item in whole_bank_review.get("items", []):
        identity = (item.get("movie_id"), item.get("question_id"))
        if identity not in decisions or identity in ready or identity in novelty:
            raise ValueError("Invalid whole-bank candidate identity")
        if item.get("ready_for_final_selection") is True:
            ready.add(identity)
        elif item.get("ready_for_final_selection") is False:
            novelty.add(identity)
        else:
            raise ValueError("Invalid whole-bank readiness decision")
    if len(ready) != 3 or len(novelty) != 1:
        raise ValueError("Unexpected provisional whole-bank decisions")

    targets = {
        (target["movie_id"], target["question_id"]): target
        for target in build_targets(source_review, bank)
    }
    if set(targets) != set(decisions):
        raise ValueError("Saved replacement targets changed")

    rows = []
    for identity in sorted(set(decisions) - ready):
        target = targets[identity]
        decision = decisions[identity]
        if identity in novelty:
            lane = "novelty"
        else:
            evidence_decision = evidence.get(identity)
            if evidence_decision is None:
                raise ValueError("Unresolved target lacks an evidence decision")
            lane = "intent" if evidence_decision == "accept" else "evidence"
        saved = bank.load(target["movie_id"])
        if saved is None:
            raise ValueError("Saved quiz bank disappeared")
        artifacts = {
            "source_review": source_sha,
            "whole_bank_review": whole_bank_sha,
        }
        if identity in evidence:
            artifacts["evidence_review"] = evidence_sha
        rows.append(
            CompletionTarget(
                movie_id=target["movie_id"],
                title=target["title"],
                question_id=target["question_id"],
                old_question=target["old_question"],
                old_answer=decision["answer"],
                replacement_brief=target["replacement_brief"],
                bank_version=saved["version"],
                bank_sha256=_bank_sha256(saved),
                lane=lane,
                originating_artifacts=artifacts,
            )
        )
    return CompletionManifest(
        policy=POLICY,
        source_review_sha256=source_sha,
        evidence_review_sha256=evidence_sha,
        whole_bank_review_sha256=whole_bank_sha,
        items=rows,
    )


def load_intent_contracts(path: Path, *, manifest: CompletionManifest):
    payload = json.loads(Path(path).read_text())
    if (
        not isinstance(payload, dict)
        or set(payload) != {"policy", "status", "manifest_sha256", "items"}
        or payload.get("policy") != CONTRACT_POLICY
        or payload.get("status") != "reviewed"
        or payload.get("manifest_sha256") != digest(manifest.model_dump(mode="json"))
        or not isinstance(payload.get("items"), list)
    ):
        raise ValueError("Expected reviewed quiz replacement intent contracts")
    contracts = [NarrativeIntent.model_validate(item) for item in payload["items"]]
    expected = {
        item.question_id for item in manifest.items if item.lane in ("intent", "evidence")
    }
    identities = [item.question_id for item in contracts]
    if len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("Intent contracts do not match the generative target scope")
    return {item.question_id: item for item in contracts}
