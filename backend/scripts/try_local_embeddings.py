"""Compare invented teaching descriptions; this is not a movie search index."""

import asyncio

import httpx

from movie_companion.embedding_learning import embed_texts
from movie_companion.vector_math import cosine_similarity


MODEL = "nomic-embed-text:v1.5"
DESCRIPTIONS = [
    "A reflective science fiction story about astronauts exploring distant planets.",
    "A warm comedy about a family preparing a chaotic holiday dinner.",
    "A tense mystery about a detective investigating a disappearance in a small town.",
]
QUERY = "A thoughtful film about exploring space."


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        documents = await embed_texts(
            client, model=MODEL,
            texts=[f"search_document: {text}" for text in DESCRIPTIONS],
        )
        queries = await embed_texts(
            client, model=MODEL, texts=[f"search_query: {QUERY}"],
        )
    print(f"Model: {MODEL}; vectors: {len(documents)}; dimensions: {len(documents[0])}")
    print(f"Question: {QUERY}")
    for text, vector in zip(DESCRIPTIONS, documents):
        print(f"{cosine_similarity(queries[0], vector):.4f} | {text}")


if __name__ == "__main__":
    asyncio.run(main())
