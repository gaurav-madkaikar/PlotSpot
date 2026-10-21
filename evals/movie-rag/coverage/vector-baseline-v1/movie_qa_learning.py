"""Learner-owned question pipeline called by the real movie-page endpoint."""

import httpx
from collections.abc import Callable

from .embedding_learning import embed_texts
from .grounding_learning import GroundedAnswer, answer_from_hits
from .retrieval_learning import EmbeddedPassage, RetrievalHit, retrieve_passages


async def answer_movie_question(
    client: httpx.AsyncClient, *, question: str, passages: list[EmbeddedPassage],
    movie_id: int, allow_spoilers: bool, embedding_model: str, chat_model: str,
    on_retrieved: Callable[[list[RetrievalHit]], None] | None = None,
) -> GroundedAnswer:
    """Learner slice: query embedding → scoped top-3 retrieval → grounded answer.

    The service supplies eligible, stored passages and bounded inputs. Embed
    [f"search_query: {question}"], take the first vector, retrieve with the movie,
    model and spoiler permission, then await answer_from_hits. Return its result.
    This function is used by POST /api/movies/{movie_id}/questions.
    """
    response = await embed_texts(
        client=client,
        model=embedding_model,
        texts=[f"search_query: {question}"]
    )
    query_vector = response[0]
    hits = retrieve_passages(
        query_vector=query_vector,
        passages=passages,
        query_model=embedding_model,
        movie_id=movie_id,
        allow_spoilers=allow_spoilers,
        k=3
    )
    # Optional observation for evaluations; app callers do not need a callback.
    if on_retrieved is not None:
        on_retrieved(list(hits))
    return await answer_from_hits(
        client=client,
        question=question,
        hits=hits,
        model=chat_model
    )
