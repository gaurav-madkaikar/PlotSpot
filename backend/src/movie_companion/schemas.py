from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CastCredit(BaseModel):
    name: str
    character: str | None = None
    profile_url: str | None = Field(default=None, pattern=r"^https://image\.tmdb\.org/t/p/w185/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$")


class CreativeCredit(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: Literal["Writer", "Screenplay", "Story", "Composer", "Cinematographer"]


class MovieTrailer(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    youtube_key: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    official: bool = Field(strict=True)


class MovieMetadata(BaseModel):
    version: Literal[1] = 1
    release_date: date | None = None
    spoken_languages: list[str] = Field(default_factory=list, max_length=100)
    production_companies: list[str] = Field(default_factory=list, max_length=100)
    production_countries: list[str] = Field(default_factory=list, max_length=100)
    budget: int | None = Field(default=None, strict=True, ge=0)
    revenue: int | None = Field(default=None, strict=True, ge=0)
    vote_average: float | None = Field(default=None, strict=True, ge=0, le=10, allow_inf_nan=False)
    vote_count: int | None = Field(default=None, strict=True, ge=0)
    status: str | None = None
    original_title: str | None = None
    cast_credits: list[CastCredit] = Field(default_factory=list, max_length=12)
    presentation_version: Literal[1] | None = None
    creative_credits: list[CreativeCredit] = Field(default_factory=list, max_length=20)
    trailer: MovieTrailer | None = None


class Movie(BaseModel):
    """The movie contract, independent of the eventual catalog provider."""

    id: int = Field(gt=0)
    title: str
    detail_metadata: MovieMetadata | None = None
    vote_average: float | None = Field(default=None, strict=True, ge=0, le=10, allow_inf_nan=False)
    vote_count: int | None = Field(default=None, strict=True, ge=0)
    adult: bool | None = Field(default=None, strict=True)
    year: int | None = Field(default=None, ge=1888, le=2100)
    runtime_minutes: int | None = Field(default=None, gt=0)
    language: str
    genres: list[str]
    director: str | None = None
    cast: list[str]
    overview: str
    tagline: str
    keywords: list[Annotated[str, Field(strict=True, min_length=1, max_length=200)]] = Field(default_factory=list, max_length=50)
    alternative_titles: list[Annotated[str, Field(strict=True, min_length=1, max_length=200)]] = Field(default_factory=list, max_length=30)
    cover_url: str | None = None
    source: Literal["demo", "tmdb"] = "demo"
    artwork_kind: Literal["illustration", "poster", "placeholder"] = "illustration"


class SearchPerson(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    known_for_department: str | None = None
    known_for_titles: list[str] = Field(default_factory=list, max_length=5)


class MovieSearchResponse(BaseModel):
    items: list[Movie]
    total: int
    data_source: Literal["demo", "tmdb"] = "demo"
    limited: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=40)
    total_pages: int = Field(default=1, ge=0)
    indexed_movies: int | None = None
    match_type: Literal["browse", "title_cast", "typo", "genre", "semantic", "keyword"] = "title_cast"
    applied_genres: list[str] = Field(default_factory=list, max_length=20)
    matched_query: str | None = None
    prepared_at: str | None = None
    partial: bool = False
    people: list[SearchPerson] = Field(default_factory=list, max_length=20)
    selected_person: SearchPerson | None = None
    person_role: Literal['actor', 'director'] | None = None
    search_token: str | None = None
    snapshot_reset: bool = False


class SearchSuggestion(BaseModel):
    label: str
    kind: Literal["movie", "actor", "director"]
    movie_ids: list[int]
    score: float = Field(ge=0, le=1)


class SuggestionResponse(BaseModel):
    items: list[SearchSuggestion]
    indexed_movies: int
    limited: Literal[True] = True
