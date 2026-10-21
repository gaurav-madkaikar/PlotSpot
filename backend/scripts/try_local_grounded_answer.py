"""Fictional retrieval-to-answer example; requires the learner's prompt function."""

import asyncio

import httpx

from movie_companion.embedding_learning import embed_texts
from movie_companion.grounding_learning import answer_from_hits
from movie_companion.retrieval_learning import EmbeddedPassage, retrieve_passages
from try_local_retrieval import MODEL, MOVIE_ID, NOTES, QUESTION


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        vectors = await embed_texts(client, model=MODEL, texts=[f"search_document: {note[3]}" for note in NOTES])
        query = (await embed_texts(client, model=MODEL, texts=[f"search_query: {QUESTION}"]))[0]
        passages = [EmbeddedPassage(
            passage_id=note[0], movie_id=note[1], text=note[3], vector=vector,
            embedding_model=MODEL, source_label="Synthetic authored cinema-programme notes",
            spoiler_status=note[2],
        ) for note, vector in zip(NOTES, vectors)]
        hits = retrieve_passages(query, passages, query_model=MODEL, movie_id=MOVIE_ID, k=2)
        answer = await answer_from_hits(client, model="llama3.2:3b", question=QUESTION, hits=hits)
    print("FICTIONAL TEACHING DATA — not real movie reporting")
    print(f"Question: {QUESTION}")
    print(f"Status: {answer.status}")
    print(f"Answer: {answer.answer}")
    print("Cited evidence:")
    for hit in hits:
        if hit.passage.passage_id in answer.citation_ids:
            print(f"[{hit.passage.passage_id}] {hit.passage.source_label}: {hit.passage.text}")


if __name__ == "__main__":
    asyncio.run(main())
