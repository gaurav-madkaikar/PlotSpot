"""Read-only semantic discovery: hard constraints first, similarity second."""
import asyncio
import math
from collections import OrderedDict
from pathlib import Path
from time import monotonic

import httpx
from pydantic import BaseModel, Field, field_validator

from .local_models import verify_local_model
from .embedding_learning import embed_texts
from .schemas import Movie
from .semantic_catalog import DEFAULT_PATH, MODEL, read_index
from .vector_math import cosine_similarity


class DiscoveryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    genre: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=40)
    max_runtime: int | None = Field(default=None, ge=1, le=600)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Describe the kind of film you want")
        return value.strip()


class DiscoveryResult(BaseModel):
    items: list[Movie]
    indexed_movies: int
    eligible_movies: int
    prepared_at: str
    limited: bool = True


class DiscoveryError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def eligible(movie: Movie, request: DiscoveryRequest) -> bool:
    genre = (request.genre or "").strip().casefold()
    language = (request.language or "").strip().casefold()
    return (
        (not genre or genre in {g.casefold() for g in movie.genres})
        and (not language or language == movie.language.casefold())
        and (request.max_runtime is None or (movie.runtime_minutes is not None and movie.runtime_minutes <= request.max_runtime))
    )


class SemanticSearch:
    def __init__(self, ollama: httpx.AsyncClient, *, path: Path = DEFAULT_PATH, slot: asyncio.Lock | None = None, hybrid=None, verify_model=False):
        self.hybrid = hybrid
        self.verify_model = verify_model
        self._verified = False
        self._snapshot = None
        self._snapshot_stat = None
        self.ollama, self.path = ollama, path
        self.slot = slot if slot is not None else asyncio.Lock()
        # Query vectors only, not user preferences or conversation memory.
        self.pending: dict[str, asyncio.Task[list[float]]] = {}
        self.cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()

    async def catalog_snapshot(self):
        stat = self.path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if signature != self._snapshot_stat:
            snapshot = await asyncio.to_thread(read_index, self.path)
            self._snapshot, self._snapshot_stat = snapshot, signature
        return self._snapshot

    async def search(self, request: DiscoveryRequest) -> DiscoveryResult:
        try:
            index = await asyncio.to_thread(read_index, self.path)
        except (OSError, ValueError):
            raise DiscoveryError(503, "Meaning-based discovery is not ready yet. Title and cast search is still available.") from None
        candidates = [(m, v) for m, v in zip(index.movies, index.vectors) if eligible(m, request)]
        metadata = dict(indexed_movies=len(index.movies), eligible_movies=len(candidates), prepared_at=index.prepared_at)
        if not candidates:
            return DiscoveryResult(items=[], **metadata)
        query = request.query
        vector = await self.query_vector(query, len(index.vectors[0]))
        try:
            ranked = sorted(candidates, key=lambda item: (-cosine_similarity(vector, item[1]), item[0].id))
        except ValueError:
            raise DiscoveryError(502, "Search results could not be verified. Please try again.") from None
        # Similarity is relative ranking, not a calibrated confidence percentage.
        return DiscoveryResult(items=[m for m, _ in ranked[:6]], **metadata)

    async def query_vector(self, query: str, dimension: int) -> list[float]:
        cached = self.cache.get(query)
        if cached and cached[0] > monotonic():
            vector = cached[1]
            self.cache.move_to_end(query)
        else:
            task = self.pending.get(query)
            if task is None:
                if self.slot.locked() or self.pending:
                    raise DiscoveryError(409, "Another AI request is running. Try again shortly.")
                task = asyncio.create_task(self._embed(query, dimension))
                self.pending[query] = task
                def finished(completed):
                    self.pending.pop(query, None)
                    # Observe failures even if all HTTP callers disconnected.
                    if not completed.cancelled():
                        completed.exception()
                task.add_done_callback(finished)
            # A disconnected viewer cannot cancel work another viewer awaits.
            vector = await asyncio.shield(task)
        return vector

    async def _embed(self, query: str, dimension: int) -> list[float]:
        try:
            async with asyncio.timeout(30), self.slot:
                if self.verify_model and not self._verified:
                    await verify_local_model(self.ollama, MODEL)
                    self._verified = True
                vector = (await embed_texts(self.ollama, model=MODEL, texts=["search_query: " + query]))[0]
            if len(vector) != dimension or not math.isfinite(sum(v * v for v in vector)):
                raise ValueError("Embedding dimension or norm mismatch")
        except TimeoutError:
            raise DiscoveryError(504, "Discovery took too long. Please try again.") from None
        except httpx.HTTPError:
            raise DiscoveryError(503, "Meaning-based search is temporarily unavailable. Please try again.") from None
        except ValueError:
            raise DiscoveryError(502, "Search results could not be verified. Please try again.") from None
        self.cache[query] = (monotonic() + 300, vector)
        self.cache.move_to_end(query)
        while len(self.cache) > 64:
            self.cache.popitem(last=False)
        return vector
