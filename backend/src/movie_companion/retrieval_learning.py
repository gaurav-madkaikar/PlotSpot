"""Inspectable in-memory retrieval; synthetic exercises are not app evidence."""

from dataclasses import dataclass
import math
from typing import Literal

from .vector_math import cosine_similarity
from .passage_location import PassageLocation


@dataclass(frozen=True)
class EmbeddedPassage:
    passage_id: str
    movie_id: int
    text: str
    vector: list[float]
    embedding_model: str
    source_label: str
    spoiler_status: Literal["safe", "spoiler", "unknown"] = "unknown"
    section_title: str = "Unclassified"
    section_category: str = "other"
    location: PassageLocation | None = None


@dataclass(frozen=True)
class RetrievalHit:
    passage: EmbeddedPassage
    score: float


def rank_passages(
    query_vector: list[float], passages: list[EmbeddedPassage], *, k: int
) -> list[RetrievalHit]:
    """Learner slice: score each passage, sort by (-score, passage_id), take k.

    Inputs are validated and scoped by retrieve_passages. Use cosine_similarity
    and retain the original passage in each RetrievalHit. Don't mutate inputs.
    """
    candidate_map: dict[str, EmbeddedPassage] = dict({passage.passage_id: passage for passage in passages})
    candidate_passages = []
    for passage in passages:
        cos_sim = cosine_similarity(query_vector, passage.vector)
        candidate_passages.append((-cos_sim, passage.passage_id))
    candidate_passages.sort(key=lambda x: (x[0], x[1]))

    candidate_passages = candidate_passages[:k]

    results: list[RetrievalHit] = []
    for neg_score, passage_id in candidate_passages:
        passage = candidate_map[passage_id]
        results.append(RetrievalHit(passage=passage, score=-neg_score))
    return results


def _validate_vector(vector: list[float], dimensions: int | None = None) -> None:
    if not isinstance(vector, list) or not vector:
        raise ValueError("Vectors must be nonempty lists")
    if dimensions is not None and len(vector) != dimensions:
        raise ValueError("Query and evidence dimensions must match")
    if not all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        for value in vector
    ):
        raise ValueError("Vectors must contain finite numbers")
    if not any(value != 0 for value in vector):
        raise ValueError("Zero vectors cannot be retrieved meaningfully")


def retrieve_passages(
    query_vector: list[float], passages: list[EmbeddedPassage], *,
    query_model: str, movie_id: int, allow_spoilers: bool = False, k: int = 3,
) -> list[RetrievalHit]:
    """Assistant-owned validation and eligibility boundary before ranking."""
    if type(k) is not int or not 1 <= k <= 6:
        raise ValueError("k must be an integer from 1 to 6")
    if type(movie_id) is not int or movie_id <= 0:
        raise ValueError("movie_id must be a positive integer")
    if not isinstance(query_model, str) or not query_model.strip():
        raise ValueError("query_model is required")
    if type(allow_spoilers) is not bool:
        raise ValueError("Spoiler permission must be a boolean")
    _validate_vector(query_vector)
    eligible = [
        passage for passage in passages
        if passage.movie_id == movie_id
        and (allow_spoilers or passage.spoiler_status == "safe")
    ]
    seen: set[str] = set()
    for passage in eligible:
        if not passage.passage_id.strip() or passage.passage_id in seen:
            raise ValueError("Eligible passage IDs must be nonempty and unique")
        seen.add(passage.passage_id)
        if not passage.text.strip() or not passage.source_label.strip():
            raise ValueError("Evidence must have text and source attribution")
        if passage.embedding_model != query_model:
            raise ValueError("Query and evidence must use the same embedding model")
        _validate_vector(passage.vector, len(query_vector))
    if not eligible:
        return []
    return rank_passages(query_vector, eligible, k=k)
