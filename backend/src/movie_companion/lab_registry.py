"""Fixed evaluation registry and bounded local artifact reader."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from pydantic import ValidationError

from .lab_contracts import EvidenceCategory, Feature, LabSuite, LabWarning
from .lab_normalizers import (
    parse_content_quality,
    parse_discussion_retrieval,
    parse_discussion_support,
    parse_fact_inspection,
    parse_multi_source_smoke,
    parse_quiz_completion,
    parse_readiness,
    parse_search,
    parse_twenty_film_audit,
)


@dataclass(frozen=True)
class SuiteDefinition:
    id: str
    title: str
    feature: Feature
    category: EvidenceCategory
    relative_path: str
    parser: Callable[[dict[str, Any], "SuiteDefinition"], LabSuite]
    required: bool = False
    gated: bool = False


_SUITES = (
    SuiteDefinition("search_development", "Search suggestions · development", "search", "development", "evals/search/report.json", parse_search),
    SuiteDefinition("search_held_out", "Search suggestions · held-out", "search", "held_out", "evals/search/report.json", parse_search),
    SuiteDefinition("content_quality_held_out", "Structured content review · held-out", "retrieval", "held_out", "evals/movie-rag/content-quality-held-out-v2-structured-v3-ollama.json", parse_content_quality),
    SuiteDefinition("fact_inspection", "Real-film fact inspection", "facts", "development", "evals/movie-rag/real-film-facts/precision-final-inspection.json", parse_fact_inspection),
    SuiteDefinition("quiz_replacement_completion", "Quiz replacement completion", "quiz", "development", "evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json", parse_quiz_completion),
    SuiteDefinition("discussion_retrieval", "Discussion retrieval comparison", "discuss", "development", "evals/movie-rag/coverage/discussion-retrieval-review.json", parse_discussion_retrieval),
    SuiteDefinition("discussion_support", "Discussion support controls", "discuss", "development", "evals/grounding/support-relations-v6.json", parse_discussion_support),
    SuiteDefinition("multi_source_smoke", "Multi-source local-model smoke", "retrieval", "smoke", "evals/movie-rag/multi-source/local-model-smoke-v1.json", parse_multi_source_smoke),
    SuiteDefinition("readiness_controls", "Content readiness controls", "readiness", "audit", "evals/movie-rag/research/readiness-v5-final.json", parse_readiness, required=True, gated=True),
    SuiteDefinition("twenty_film_audit", "Twenty-film reviewability audit", "readiness", "audit", "evals/movie-rag/expanded-20/final-review-audit-v2.json", parse_twenty_film_audit, required=True, gated=True),
)


def registered_suites() -> tuple[SuiteDefinition, ...]:
    return _SUITES


def _safe_file(project_root: Path, relative_path: str, max_bytes: int) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid_source")
    root = project_root.resolve()
    candidate = root / relative
    if not candidate.exists():
        raise FileNotFoundError
    if candidate.is_symlink():
        raise ValueError("invalid_source")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("invalid_source")
    size = resolved.stat().st_size
    if size < 2 or size > max_bytes:
        raise ValueError("invalid_source")
    return resolved


def _unavailable(definition: SuiteDefinition, status: Literal["error", "no_data"], warning: LabWarning) -> LabSuite:
    return LabSuite(
        id=definition.id,
        title=definition.title,
        feature=definition.feature,
        category=definition.category,
        status=status,
        gated=definition.gated,
        recorded_at=None,
        metrics=[],
        source_label=definition.relative_path,
        limitations=["This registered evaluation could not be loaded."],
        warnings=[warning],
    )


def load_evaluation_suites(
    project_root: Path,
    definitions: Sequence[SuiteDefinition] | None = None,
    max_bytes: int = 2_000_000,
) -> tuple[list[LabSuite], list[LabWarning]]:
    if not 1 <= max_bytes <= 5_000_000:
        raise ValueError("Invalid report size limit")
    suites: list[LabSuite] = []
    warnings: list[LabWarning] = []
    for definition in definitions or _SUITES:
        try:
            source = _safe_file(Path(project_root), definition.relative_path, max_bytes)
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid_source")
            suites.append(definition.parser(payload, definition))
        except FileNotFoundError:
            warning = LabWarning(
                code="missing_source",
                suite_id=definition.id,
                message="The registered evaluation report is unavailable.",
            )
            warnings.append(warning)
            suites.append(_unavailable(definition, "error" if definition.required else "no_data", warning))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, ValidationError):
            warning = LabWarning(
                code="invalid_source",
                suite_id=definition.id,
                message="The registered evaluation report is invalid or unsupported.",
            )
            warnings.append(warning)
            suites.append(_unavailable(definition, "error", warning))
    return suites, warnings
