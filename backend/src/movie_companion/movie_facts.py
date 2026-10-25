"""Production background belongs in facts, separate from the story quiz."""
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from .source_registry import valid_source_url

from .movie_questions import MovieQuestionService, QuestionCitation
from .movie_quiz import build_supported_items


PRODUCTION = (
    {"id": "real-cornfield", "question": "How many acres of corn did production designer Nathan Crowley plant for Interstellar's cornfield scene?", "title": "A cornfield grown for the camera",
     "options": ["50 acres", "500 acres", "5,000 acres", "No real corn"],
     "display_text": "Production designer Nathan Crowley planted 500 acres (200 hectares) of real corn for the film’s cornfield scene.",
     "correct_index": 1, "fact": "500", "source_phrase": "planted 500 acres"},
    {"id": "secret-title", "question": "Under what name was Interstellar filmed as a security measure?", "title": "A secret title with a family connection",
     "options": ["Flora's Letter", "Endurance", "The Dust Bowl", "Project Saturn"],
     "display_text": "Interstellar was filmed under the secret name Flora’s Letter. Flora is one of Christopher Nolan and producer Emma Thomas’s four children.",
     "correct_index": 0, "fact": "flora", "source_phrase": "flora being one of nolan's four children"},
)


class MovieFact(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    citations: list[QuestionCitation] = Field(min_length=1, max_length=3)


class ReadingSource(BaseModel):
    kind: Literal["research", "early_draft", "interview", "article"]
    title: str = Field(min_length=1, max_length=200)
    source_ref: str = Field(max_length=500)
    publisher: str = Field(min_length=1, max_length=100)
    date: str = Field(max_length=20)
    authors: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(max_length=250)
    retrieved_at: str = Field(max_length=40)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source_ref")
    @classmethod
    def reviewed_url(cls, value):
        if not valid_source_url(value):
            raise ValueError("Unreviewed source URL")
        return value


class MovieFacts(BaseModel):
    reading_sources: list[ReadingSource] = Field(default_factory=list, max_length=4)
    prepared_at: str | None = None
    content_version: str | None = None
    status: str = Field(pattern="^(ready|source_unavailable|spoiler_permission_required)$")
    message: str
    items: list[MovieFact] = Field(default_factory=list, max_length=12)


async def create_facts(service: MovieQuestionService, *, movie_id: int, allow_spoilers: bool) -> MovieFacts:
    result = await build_supported_items(service, movie_id=movie_id, allow_spoilers=allow_spoilers, bank=PRODUCTION, evidence_purpose="background")
    entries = {item["id"]: item for item in PRODUCTION}
    return MovieFacts(status=result.status, message="Production background from Wikipedia; additional web sources are not connected yet." if result.status == "ready" else result.message, items=[MovieFact(id=item.id, title=entries[item.id]["title"], text=entries[item.id]["display_text"], citations=item.citations) for item in result.items])
