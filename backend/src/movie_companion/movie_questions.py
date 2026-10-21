"""Bounded source-backed movie questions; model text has no action capabilities."""

import asyncio
from dataclasses import asdict
from collections import OrderedDict
import json
from pathlib import Path
from typing import Literal
from time import monotonic

import httpx
from pydantic import BaseModel, Field, StrictBool, field_validator, model_serializer

from .evidence_store import EvidenceStore
from .grounding_learning import GroundedAnswer, _parse_answer
from .ingestion_learning import ingest_source
from .source_sections import matches_purpose
from .source_registry import valid_source_url, SCRIPT_URL, SCRIPT_URLS
from .movie_qa_learning import answer_movie_question
from .wikipedia_source import MOVIE_ARTICLES, fetch_movie_source


class MovieQuestion(BaseModel):
    question: str = Field(strict=True, min_length=1, max_length=1000)
    allow_spoilers: StrictBool = False

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value.strip()


class QuestionCitation(BaseModel):
    source_kind: Literal['reviewed','web'] = 'reviewed'
    source_verified: bool = Field(default=False,strict=True)
    passage_id: str = Field(max_length=64)
    source_label: str = Field(max_length=200)
    source_ref: str = Field(max_length=500)

    @field_validator("source_ref")
    @classmethod
    def reviewed_url(cls, value):
        from urllib.parse import urlsplit
        if not valid_source_url(value) or urlsplit(value).hostname=='imsdb.com':
            raise ValueError("Unreviewed source URL")
        return value
    @model_serializer(mode='wrap')
    def serialize_acquisition(self,handler):
        data=handler(self)
        if self.source_kind=='reviewed' and not self.source_verified:
            data.pop('source_kind',None);data.pop('source_verified',None)
        return data
    revision: str = Field(max_length=100)
    excerpt: str = Field(max_length=600)


class ScriptContext(BaseModel):
    source_ref: str = Field(pattern=r'^https://imsdb\.com/scripts/[^/?#]+\.html$')
    @field_validator('source_ref')
    @classmethod
    def screenplay_url(cls,value):
        from .web_corpus_store import registered_url
        if value not in SCRIPT_URLS and not registered_url(value):raise ValueError('Unverified screenplay URL')
        return value
    version: str = Field(max_length=120)
    released_film_verified: Literal[False] = False


class MovieAnswer(BaseModel):
    status: str = Field(pattern="^(answered|insufficient_evidence|source_unavailable|spoiler_permission_required)$")
    answer: str = Field(max_length=4000)
    answer_kind: Literal["event", "interpretation"] = "event"
    source_coverage: dict | None = None
    script_context: ScriptContext | None = None
    citations: list[QuestionCitation] = Field(default_factory=list, max_length=3)


class QuestionError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class MovieQuestionService:
    embedding_model = "nomic-embed-text:v1.5"
    chat_model = "llama3.2:3b"
    chunk_settings = {"max_chars": 600, "overlap_chars": 100}

    def __init__(self, wiki: httpx.AsyncClient, ollama: httpx.AsyncClient, *, store=None):
        self.wiki, self.ollama, self.store = wiki, ollama, store
        self.story = None
        self.corpus = None
        self.identity_loader = None
        self.source_traces = {}
        self.slot = asyncio.Lock()
        self.source_cache = OrderedDict()

    async def ask(self, movie_id: int, request: MovieQuestion, *, evidence_phrase: str | None = None, evidence_purpose: str | None = None) -> MovieAnswer:
        if movie_id not in MOVIE_ARTICLES:
            return MovieAnswer(status="source_unavailable", answer="A reviewed discussion source is not available for this film yet.")
        # Whole article is unknown: enforce consent before any source/model I/O.
        if not request.allow_spoilers:
            return MovieAnswer(status="spoiler_permission_required", answer="This source can contain story details. Allow spoilers above before asking a question.")
        if self.slot.locked():
            raise QuestionError(409, "Another movie question is being answered. Please try again shortly.")
        async with self.slot:
            try:
                async with asyncio.timeout(180):
                    return await self._answer(movie_id, request, evidence_phrase=evidence_phrase, evidence_purpose=evidence_purpose)
            except NotImplementedError as exc:
                raise QuestionError(503, "The movie question flow is still being prepared. Please try again after it is ready.") from exc
            except TimeoutError as exc:
                raise QuestionError(504, "This question took too long. Please try again.") from exc
            except httpx.HTTPError as exc:
                raise QuestionError(503, "A source or the local AI service is unavailable. Please try again.") from exc
            except (ValueError, OSError) as exc:
                raise QuestionError(502, "A reliable answer could not be verified. Please try another question.") from exc

    async def load_evidence(self, movie_id):
        cached = self.source_cache.get(movie_id)
        if cached is None or cached[0] <= monotonic():
            source = await fetch_movie_source(self.wiki, movie_id=movie_id)
            if source.movie_id != movie_id:
                raise ValueError("Source movie mismatch")
            self.source_cache[movie_id] = (monotonic() + 300, source)
            self.source_cache.move_to_end(movie_id)
            while len(self.source_cache) > 10:
                self.source_cache.popitem(last=False)
        else:
            source = cached[1]
        if self.store is None:
            path = Path(__file__).resolve().parents[3] / "data/chroma/app"
            self.store = await asyncio.to_thread(EvidenceStore, path)
        await ingest_source(self.ollama, store=self.store, source=source, model=self.embedding_model, **self.chunk_settings)
        passages = await asyncio.to_thread(self.store.load_snapshot, source, model=self.embedding_model, **self.chunk_settings)
        return source, passages

    async def _answer(self, movie_id, request, *, evidence_phrase=None, evidence_purpose=None):
        if self.corpus is not None and evidence_phrase is None and evidence_purpose is None:
            from .multi_source_pipeline import answer_multi_source
            return await answer_multi_source(self,movie_id,request)
        source, passages = await self.load_evidence(movie_id)
        if self.story is not None and self.story.enabled(movie_id) and self.story.handles(request.question) and evidence_phrase is None and evidence_purpose is None:
            return await self.story.discuss(self.ollama, source=source, passages=passages, question=request.question)
        eligible = [p for p in passages if p.movie_id == movie_id and (request.allow_spoilers or p.spoiler_status == "safe")]
        # Curated quiz/fact banks can select reviewed source statements before
        # semantic ranking. This internal hint is never accepted from API input.
        # Missing statements leave no evidence; the pipeline must abstain.
        if evidence_purpose is not None:
            eligible = [p for p in eligible if matches_purpose(p.section_category, evidence_purpose)]
        if evidence_phrase is not None:
            eligible = [p for p in eligible if evidence_phrase.casefold() in p.text.casefold()]
        result = await answer_movie_question(
            self.ollama, question=request.question, passages=eligible, movie_id=movie_id,
            allow_spoilers=request.allow_spoilers, embedding_model=self.embedding_model, chat_model=self.chat_model,
        )
        if not isinstance(result, GroundedAnswer):
            raise ValueError("Pipeline must return a validated grounded answer")
        # Revalidate result independently of the learner pipeline's choices.
        checked = _parse_answer(json.dumps(asdict(result)), {p.passage_id for p in eligible})
        by_id = {p.passage_id: p for p in eligible}
        citations = [QuestionCitation(
            passage_id=identifier, source_label=source.source_label,
            source_ref=source.source_ref, revision=source.revision,
            excerpt=by_id[identifier].text[:600],
        ) for identifier in checked.citation_ids]
        return MovieAnswer(status=checked.status, answer=checked.answer, citations=citations)
