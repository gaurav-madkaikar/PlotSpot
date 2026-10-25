"""Learner-owned embedding request, kept separate from chat generation."""

import math

import httpx


async def embed_texts(
    client: httpx.AsyncClient, *, model: str, texts: list[str]
) -> list[list[float]]:
    """Embed nonblank texts; preserve HTTP errors and reject invalid vectors.

    Use /api/embed with truncate=False. Require one finite, nonzero,
    equal-dimensional vector per input. Prefixes are supplied by the caller.
    """
    if not isinstance(texts, list) or not texts:
        raise ValueError("Input texts must be a nonempty list")
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Each input text must be a nonblank string")
    response = await client.post(
        "/api/embed",
        json={
            "model": model,
            "input": texts,
            "truncate": False,
        },
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON response object")
    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or not all(
        isinstance(vec, list) for vec in embeddings
    ):
        raise ValueError("Expected a list of embedding vectors")
    if len(embeddings) != len(texts):
        raise ValueError("Number of embeddings must match number of input texts")
    for vec in embeddings:
        if not vec or not all(
            not isinstance(coord, bool)
            and isinstance(coord, (int, float))
            and math.isfinite(coord)
            for coord in vec
        ):
            raise ValueError("Each embedding must contain finite numeric coordinates")
        if not any(coord != 0 for coord in vec):
            raise ValueError("Each embedding must be a nonzero vector")
    first_len = len(embeddings[0])
    if not all(len(vec) == first_len for vec in embeddings):
        raise ValueError("All embedding vectors must have the same dimension")
    return embeddings
