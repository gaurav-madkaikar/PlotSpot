"""Validated name-search candidates; these are not hydrated movie records."""
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

Identity = Annotated[int, Field(strict=True, gt=0)]


class MovieNameCandidate(BaseModel):
    id: Identity
    title: str = Field(min_length=1, max_length=300)
    adult: bool | None = Field(default=None, strict=True)
    release_date: str | None = Field(default=None, max_length=20)
    overview: str = Field(default='', max_length=20000)
    original_title: str | None = Field(default=None, max_length=300)
    original_language: str | None = Field(default=None, max_length=20)
    poster_path: str | None = Field(default=None, max_length=500)
    vote_average: float | None = Field(default=None, strict=True, ge=0, le=10, allow_inf_nan=False)
    vote_count: int | None = Field(default=None, strict=True, ge=0)
    genre_ids: list[Identity] = Field(default_factory=list, max_length=40)


class PersonNameCandidate(BaseModel):
    id: Identity
    name: str = Field(min_length=1, max_length=200)
    adult: bool | None = Field(default=None, strict=True)
    known_for_department: str | None = Field(default=None, max_length=100)
    known_for_titles: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="before")
    @classmethod
    def known_titles(cls, value):
        if isinstance(value, dict) and "known_for" in value:
            records = value["known_for"]
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                raise ValueError("Invalid known works")
            value = {**value, "known_for_titles": [r["title"] for r in records if isinstance(r.get("title"), str)][:5]}
        return value


Candidate = TypeVar("Candidate")


class NamePage(BaseModel, Generic[Candidate]):
    items: list[Candidate]
    page: int
    total_pages: int
    limited: bool = False


def name_query(query, page):
    if not isinstance(query, str) or not query.strip() or len(query.strip()) > 120:
        raise ValueError("Name query must contain 1 to 120 characters")
    if type(page) is not int or not 1 <= page <= 100:
        raise ValueError("Name search supports pages 1 to 100")
    return query.strip()


def name_page(payload, requested_page, candidate_type):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("Invalid name-search results")
    if len(payload["results"]) > 20:
        raise ValueError("Name-search page exceeds work bound")
    page, total = payload.get("page"), payload.get("total_pages")
    if type(page) is not int or page != requested_page or type(total) is not int or not 0 <= total <= 1_000_000:
        raise ValueError("Invalid name-search pagination")
    items, seen = [], set()
    for record in payload["results"]:
        if not isinstance(record, dict) or type(record.get("adult", False)) is not bool:
            raise ValueError("Invalid name candidate")
        candidate = candidate_type.model_validate(record)
        if candidate.id not in seen:
            items.append(candidate)
            seen.add(candidate.id)
    return NamePage[candidate_type](items=items, page=page, total_pages=min(total, 100), limited=total > 100)


def acting_movie_ids(cast):
    """Credit records are validated by the provider before reaching this helper."""
    return list(dict.fromkeys(record["id"] for record in cast))


def director_movie_ids(crew: list[dict]) -> list[int]:
    """Only the exact Director job establishes a directing credit."""
    return list(dict.fromkeys(record["id"] for record in crew if record["job"] == "Director"))
