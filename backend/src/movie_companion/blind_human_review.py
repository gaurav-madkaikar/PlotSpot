"""Build and score arm-blinded human review packets for RAG outputs."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


POLICY = "plotspot-blind-rag-review-v1"


class HumanJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    correctness: Literal["correct", "partially_correct", "incorrect"] | None = None
    citation_support: Literal[
        "fully_supported", "partly_supported", "unsupported", "not_applicable"
    ] | None = None
    completeness: Literal["complete", "incomplete", "not_applicable"] | None = None
    abstention: Literal["appropriate", "inappropriate", "not_applicable"] | None = None
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def coherent(self):
        supplied = (
            self.correctness,
            self.citation_support,
            self.completeness,
            self.abstention,
        )
        if any(value is None for value in supplied) and any(value is not None for value in supplied):
            raise ValueError("Complete all four review fields or leave all four blank")
        return self


class BlindReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    blind_id: str = Field(pattern=r"^R[0-9]{3}$")
    movie: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=1000)
    response_status: Literal["answered", "insufficient_evidence", "invalid_response"]
    answer: str = Field(min_length=1, max_length=4000)
    evidence: list[str] = Field(max_length=3)
    review: HumanJudgement


class BlindReviewPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    policy: Literal[POLICY]
    source_run_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    instructions: list[str] = Field(min_length=1, max_length=12)
    items: list[BlindReviewItem] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({item.blind_id for item in self.items}) != len(self.items):
            raise ValueError("Blind review IDs must be unique")
        return self


def canonical_sha256(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


def packet_content_sha256(packet_data: dict) -> str:
    """Bind the displayed task while allowing only review fields to be filled."""
    packet = BlindReviewPacket.model_validate(packet_data).model_dump()
    for item in packet["items"]:
        item["review"] = HumanJudgement().model_dump()
    return canonical_sha256(packet)


def build_blind_packet(report: dict, *, passage_text: dict[str, str], seed: int) -> tuple[dict, dict]:
    """Return a randomized review packet and a separate arm-decoding key."""
    if type(seed) is not int:
        raise ValueError("Review seed must be an integer")
    arms = []
    for case in report.get("cases", []):
        for arm in ("direct", "specialist"):
            sample = case.get(arm, {})
            answer = sample.get("answer")
            status = answer.get("status") if isinstance(answer, dict) else "invalid_response"
            text = answer.get("answer") if isinstance(answer, dict) else "No valid answer was returned."
            cited = answer.get("citation_ids", []) if isinstance(answer, dict) else []
            retrieved = sample.get("retrieved_ids", [])
            ordered_ids = list(dict.fromkeys([*cited, *retrieved]))[:3]
            evidence = [passage_text[identifier] for identifier in ordered_ids if identifier in passage_text]
            arms.append({
                "case_id": case["id"],
                "arm": arm,
                "expected_status": case["expected_status"],
                "movie": case["title"],
                "question": case["question"],
                "response_status": status,
                "answer": text,
                "evidence": evidence,
            })
    if not arms:
        raise ValueError("Benchmark report has no reviewable outputs")
    rng = random.Random(seed)
    rng.shuffle(arms)
    items, mapping = [], []
    for index, row in enumerate(arms, 1):
        blind_id = f"R{index:03}"
        items.append({
            "blind_id": blind_id,
            "movie": row["movie"],
            "question": row["question"],
            "response_status": row["response_status"],
            "answer": row["answer"],
            "evidence": row["evidence"],
            "review": HumanJudgement().model_dump(),
        })
        mapping.append({key: row[key] for key in ("case_id", "arm", "expected_status")} | {"blind_id": blind_id})
    packet = BlindReviewPacket(
        policy=POLICY,
        source_run_sha256=canonical_sha256(report),
        instructions=[
            "Judge only the displayed answer and evidence; do not look up the hidden arm mapping.",
            "Correctness asks whether the answer resolves the question accurately.",
            "Citation support asks whether the displayed evidence supports every factual claim.",
            "Completeness asks whether all requested parts and necessary units are present.",
            "For an abstention, mark abstention appropriate only when the displayed evidence cannot answer the question.",
            "Fill all four review fields for every item; notes are optional.",
        ],
        items=items,
    ).model_dump()
    key = {
        "policy": POLICY,
        "seed": seed,
        "source_run_sha256": packet["source_run_sha256"],
        "packet_sha256": packet_content_sha256(packet),
        "mapping": mapping,
    }
    return packet, key


def score_blind_packet(packet_data: dict, key: dict) -> dict:
    packet = BlindReviewPacket.model_validate(packet_data)
    if packet_content_sha256(packet.model_dump()) != key.get("packet_sha256"):
        raise ValueError("Review packet differs from the packet bound to this key")
    mapping = {row["blind_id"]: row for row in key.get("mapping", [])}
    if set(mapping) != {item.blind_id for item in packet.items}:
        raise ValueError("Review key does not cover this packet exactly")
    rows = []
    for item in packet.items:
        review = item.review
        if any(value is None for value in (
            review.correctness, review.citation_support, review.completeness, review.abstention
        )):
            raise ValueError(f"Review {item.blind_id} is incomplete")
        hidden = mapping[item.blind_id]
        if hidden["expected_status"] == "answered":
            passed = (
                review.correctness == "correct"
                and review.citation_support == "fully_supported"
                and review.completeness == "complete"
                and review.abstention == "not_applicable"
            )
        else:
            passed = review.abstention == "appropriate"
        rows.append({
            "blind_id": item.blind_id,
            "case_id": hidden["case_id"],
            "arm": hidden["arm"],
            "expected_status": hidden["expected_status"],
            "human_pass": passed,
            "review": review.model_dump(),
        })
    summaries = {}
    for arm in ("direct", "specialist"):
        selected = [row for row in rows if row["arm"] == arm]
        counts = Counter(row["review"]["correctness"] for row in selected)
        passed = sum(row["human_pass"] for row in selected)
        summaries[arm] = {
            "cases": len(selected),
            "human_passed": passed,
            "human_pass_rate_percent": round(100 * passed / len(selected), 1),
            "correctness": dict(sorted(counts.items())),
        }
    return {
        "policy": POLICY,
        "source_run_sha256": packet.source_run_sha256,
        "packet_sha256": packet_content_sha256(packet.model_dump()),
        "summary": summaries,
        "specialist_pass_rate_delta_points": round(
            summaries["specialist"]["human_pass_rate_percent"]
            - summaries["direct"]["human_pass_rate_percent"],
            1,
        ),
        "cases": rows,
        "limitations": [
            "This is one human review unless additional completed packets are aggregated separately.",
            "The reviewer can infer some pairs from identical questions even though arm names and automated labels are hidden.",
            "The displayed evidence is bounded to three passages and may omit other retrieved context.",
        ],
    }


def render_review_form(packet_data: dict) -> str:
    packet = BlindReviewPacket.model_validate(packet_data)
    lines = [
        "# Blinded PlotSpot answer review",
        "",
        "Do not open the decoding key until every item is labelled. Use the JSON packet for machine-readable labels; this form explains the choices.",
        "",
        "## Labels",
        "",
        "- Correctness: `correct`, `partially_correct`, or `incorrect`.",
        "- Citation support: `fully_supported`, `partly_supported`, `unsupported`, or `not_applicable`.",
        "- Completeness: `complete`, `incomplete`, or `not_applicable`.",
        "- Abstention: `appropriate`, `inappropriate`, or `not_applicable`.",
        "",
    ]
    for item in packet.items:
        lines.extend([
            f"## {item.blind_id} · {item.movie}",
            "",
            f"**Question:** {item.question}",
            "",
            f"**Response status:** `{item.response_status}`",
            "",
            f"**Answer:** {item.answer}",
            "",
            "**Displayed evidence:**",
            "",
        ])
        lines.extend(f"> {text}" for text in item.evidence)
        if not item.evidence:
            lines.append("> No evidence was returned.")
        lines.extend(["", "Record the four labels in this item's `review` object in the JSON packet.", ""])
    return "\n".join(lines)
