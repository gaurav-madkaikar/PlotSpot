"""Frozen-label comparison helpers for direct and specialist movie RAG."""
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence_store import SourceDocument, snapshot_key
from .movie_questions import MovieQuestionService
from .source_sections import source_chunks


POLICY = "plotspot-orchestration-holdout-v1"
CASCADE_POLICY = "plotspot-direct-first-cascade-holdout-v2"


class BenchmarkSource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    movie_id: int = Field(gt=0)
    path: str = Field(pattern=r"^\.cache/expanded20/sources/[1-9][0-9]*\.json$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: str = Field(min_length=1, max_length=100)
    snapshot: str = Field(pattern=r"^[a-f0-9]{64}$")


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=1000)
    expected_status: Literal["answered", "insufficient_evidence"]
    reference_answer: str | None = Field(default=None, max_length=500)
    reference_excerpt: str | None = Field(default=None, max_length=600)
    relevant_passage_ids: list[str] = Field(max_length=10)
    required_phrase_groups: list[list[str]] = Field(max_length=10)

    @model_validator(mode="after")
    def valid_labels(self):
        answered = self.expected_status == "answered"
        if answered != bool(self.reference_answer and self.reference_excerpt
                            and self.relevant_passage_ids and self.required_phrase_groups):
            raise ValueError("Answerable labels require an answer, excerpt, passages and phrases")
        if len(set(self.relevant_passage_ids)) != len(self.relevant_passage_ids):
            raise ValueError("Relevant passage IDs must be unique")
        if any(not group or len(group) > 10 or any(not phrase.strip() for phrase in group)
               for group in self.required_phrase_groups):
            raise ValueError("Phrase groups must be bounded and nonblank")
        return self


class BenchmarkDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    policy: Literal[POLICY, CASCADE_POLICY]
    created_at: str = Field(min_length=1, max_length=40)
    split: Literal["holdout"]
    label_origin: str = Field(min_length=20, max_length=500)
    embedding_model: str
    chat_model: str
    chunk_settings: dict[str, int]
    sources: list[BenchmarkSource] = Field(min_length=1, max_length=20)
    cases: list[BenchmarkCase] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_and_bounded(self):
        if len({source.movie_id for source in self.sources}) != len(self.sources):
            raise ValueError("Benchmark sources must be unique")
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Benchmark cases must be unique")
        movies = {source.movie_id for source in self.sources}
        if any(case.movie_id not in movies for case in self.cases):
            raise ValueError("Every benchmark case needs a frozen source")
        if (self.embedding_model != MovieQuestionService.embedding_model
                or self.chat_model != MovieQuestionService.chat_model
                or self.chunk_settings != MovieQuestionService.chunk_settings):
            raise ValueError("Benchmark model or chunk policy changed")
        return self


def load_frozen_dataset(path: Path, *, root: Path):
    if path.stat().st_size > 200_000:
        raise ValueError("Benchmark dataset exceeds budget")
    raw = path.read_bytes()
    dataset = BenchmarkDataset.model_validate_json(raw)
    sources = {}
    for record in dataset.sources:
        source_path = (root / record.path).resolve()
        expected = (root / f".cache/expanded20/sources/{record.movie_id}.json").resolve()
        if source_path != expected or sha256(source_path.read_bytes()).hexdigest() != record.sha256:
            raise ValueError(f"Movie {record.movie_id} source snapshot changed")
        source = SourceDocument(**json.loads(source_path.read_text()))
        key = snapshot_key(source, model=dataset.embedding_model, **dataset.chunk_settings)
        if source.movie_id != record.movie_id or source.revision != record.revision or key != record.snapshot:
            raise ValueError(f"Movie {record.movie_id} source identity changed")
        sources[record.movie_id] = source

    for case in dataset.cases:
        source = sources[case.movie_id]
        key = next(item.snapshot for item in dataset.sources if item.movie_id == case.movie_id)
        chunks = source_chunks(source, **dataset.chunk_settings)
        ids = [f"{key[:32]}_{index:03}" for index in range(len(chunks))]
        if not set(case.relevant_passage_ids) <= set(ids):
            raise ValueError(f"Unknown supporting passage in {case.id}")
        if case.expected_status == "answered":
            start = source.text.find(case.reference_excerpt)
            if start < 0:
                raise ValueError(f"Reference excerpt changed in {case.id}")
            end = start + len(case.reference_excerpt)
            expected_ids = [identifier for identifier, chunk in zip(ids, chunks)
                            if min(end, chunk.end) > max(start, chunk.start)]
            if case.relevant_passage_ids != expected_ids:
                raise ValueError(f"Reference passage mapping changed in {case.id}")
            reference = f"{case.reference_answer} {case.reference_excerpt}".casefold()
            if any(not any(phrase.casefold() in reference for phrase in group)
                   for group in case.required_phrase_groups):
                raise ValueError(f"Expected phrase is outside the frozen reference in {case.id}")
    return dataset, sources, sha256(raw).hexdigest()


def project_relative_path(path: Path, *, root: Path) -> str:
    """Normalize CLI paths before recording a repository-relative artifact path."""
    return str(path.resolve().relative_to(root.resolve()))


def _percent(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def _p95(values):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * .95) - 1)] if ordered else None


def summarize_arm(rows: list[dict], arm: str) -> dict:
    samples = [row[arm] for row in rows]
    answered = [sample for row, sample in zip(rows, samples) if row["expected_status"] == "answered"]
    missing = [sample for row, sample in zip(rows, samples) if row["expected_status"] == "insufficient_evidence"]
    durations = [sample["duration_seconds"] for sample in samples]
    calls = [call for sample in samples for call in sample["calls"]]
    chats = [call for call in calls if call["endpoint"] == "/api/chat"]
    embeddings = [call for call in calls if call["endpoint"] == "/api/embed"]
    return {
        "cases": len(samples),
        "automated_passed": sum(sample["grade"]["automated_pass"] for sample in samples),
        "automated_pass_rate_percent": _percent(sum(sample["grade"]["automated_pass"] for sample in samples), len(samples)),
        "answerable_passed": sum(sample["grade"]["automated_pass"] for sample in answered),
        "answerable_total": len(answered),
        "missing_evidence_passed": sum(sample["grade"]["automated_pass"] for sample in missing),
        "missing_evidence_total": len(missing),
        "supporting_hit_at_3": sum(sample["grade"]["supporting_hit_at_3"] is True for sample in answered),
        "generation_errors": sum(sample["error"] is not None for sample in samples),
        "median_latency_seconds": round(median(durations), 3),
        "p95_latency_seconds": round(_p95(durations), 3),
        "total_latency_seconds": round(sum(durations), 3),
        "chat_calls": len(chats),
        "embedding_calls": len(embeddings),
        "prompt_tokens": sum(call.get("prompt_tokens") or 0 for call in chats),
        "output_tokens": sum(call.get("output_tokens") or 0 for call in chats),
        "ollama_duration_seconds": round(sum((call.get("total_duration_ns") or 0) / 1_000_000_000 for call in calls), 3),
        "models": sorted({call.get("model") for call in calls if call.get("model")}),
    }


def comparison(rows: list[dict]) -> dict:
    direct = summarize_arm(rows, "direct")
    specialist = summarize_arm(rows, "specialist")
    pass_delta = round(specialist["automated_pass_rate_percent"] - direct["automated_pass_rate_percent"], 1)
    latency_ratio = round(specialist["median_latency_seconds"] / direct["median_latency_seconds"], 2) if direct["median_latency_seconds"] else None
    if specialist["automated_passed"] > direct["automated_passed"]:
        conclusion = "The specialist pipeline improved automated holdout quality, with additional latency and model calls."
    elif specialist["automated_passed"] == direct["automated_passed"]:
        conclusion = "The specialist pipeline did not improve automated holdout pass count; its added latency needs a stronger quality justification."
    else:
        conclusion = "The specialist pipeline reduced automated holdout quality on this run and should not replace the direct baseline without investigation."
    return {"direct": direct, "specialist": specialist,
            "specialist_pass_rate_delta_points": pass_delta,
            "specialist_median_latency_ratio": latency_ratio,
            "conclusion": conclusion}


def render_comparison(report: dict) -> str:
    direct = report["comparison"]["direct"]
    specialist = report["comparison"]["specialist"]
    rows = [
        "# Direct versus specialist movie RAG",
        "",
        f"Run: {report['created_at']}",
        "",
        "Both arms used the same frozen source snapshots, labels, retriever, embedding model and answer model. The specialist arm additionally used context recovery and a separate support-review model.",
        "",
        "| Metric | Direct single agent | Specialist pipeline |",
        "|---|---:|---:|",
        f"| Automated pass | {direct['automated_passed']}/{direct['cases']} ({direct['automated_pass_rate_percent']}%) | {specialist['automated_passed']}/{specialist['cases']} ({specialist['automated_pass_rate_percent']}%) |",
        f"| Answerable cases | {direct['answerable_passed']}/{direct['answerable_total']} | {specialist['answerable_passed']}/{specialist['answerable_total']} |",
        f"| Missing-evidence controls | {direct['missing_evidence_passed']}/{direct['missing_evidence_total']} | {specialist['missing_evidence_passed']}/{specialist['missing_evidence_total']} |",
        f"| Supporting hit at 3 | {direct['supporting_hit_at_3']}/{direct['answerable_total']} | {specialist['supporting_hit_at_3']}/{specialist['answerable_total']} |",
        f"| Median latency | {direct['median_latency_seconds']} s | {specialist['median_latency_seconds']} s |",
        f"| P95 latency | {direct['p95_latency_seconds']} s | {specialist['p95_latency_seconds']} s |",
        f"| Chat calls | {direct['chat_calls']} | {specialist['chat_calls']} |",
        f"| Prompt / output tokens | {direct['prompt_tokens']} / {direct['output_tokens']} | {specialist['prompt_tokens']} / {specialist['output_tokens']} |",
        "",
        f"**Observed comparison:** {report['comparison']['conclusion']}",
        "",
        "## Per-case outcome",
        "",
        "| Case | Expected | Direct | Specialist | Direct latency | Specialist latency |",
        "|---|---|---|---|---:|---:|",
    ]
    for row in report["cases"]:
        direct_status = "pass" if row["direct"]["grade"]["automated_pass"] else "fail"
        specialist_status = "pass" if row["specialist"]["grade"]["automated_pass"] else "fail"
        rows.append(f"| {row['id']} | {row['expected_status']} | {direct_status} | {specialist_status} | {row['direct']['duration_seconds']} s | {row['specialist']['duration_seconds']} s |")
    rows.extend(["", "## Limits", ""])
    rows.extend(f"- {item}" for item in report["limitations"])
    rows.append("")
    return "\n".join(rows)
