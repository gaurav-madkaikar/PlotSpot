"""Retrieve pre-split fictional cinema-programme notes, not real movie facts."""

import asyncio

import httpx

from movie_companion.embedding_learning import embed_texts
from movie_companion.retrieval_learning import EmbeddedPassage, retrieve_passages


MODEL = "nomic-embed-text:v1.5"
MOVIE_ID = 900000001  # Synthetic ID used only by this teaching script.
QUESTION = "How were the spacecraft sounds made?"
NOTES = [
    ("sound", MOVIE_ID, "safe", "For the fictional film Orbit Day, the sound team recorded a washing machine and slowed its hum to create spacecraft ambience."),
    ("costumes", MOVIE_ID, "safe", "For Orbit Day, costume designers used recycled fabric and painted the suits silver."),
    ("ending", MOVIE_ID, "spoiler", "Orbit Day ends with the pilot discovering that the spacecraft sounds were a hidden message from a missing friend."),
    ("other-film", 900000002, "safe", "For the fictional film Kitchen Moon, spacecraft sounds were synthesized using a keyboard."),
]

async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        vectors = await embed_texts(
            client, model=MODEL,
            texts=[f"search_document: {note[3]}" for note in NOTES],
        )
        query = (await embed_texts(
            client, model=MODEL, texts=[f"search_query: {QUESTION}"],
        ))[0]
    passages = [
        EmbeddedPassage(
            passage_id=note[0], movie_id=note[1], text=note[3], vector=vector,
            embedding_model=MODEL, source_label="Synthetic authored cinema-programme notes",
            spoiler_status=note[2],
        )
        for note, vector in zip(NOTES, vectors)
    ]
    hits = retrieve_passages(
        query, passages, query_model=MODEL, movie_id=MOVIE_ID, k=2,
    )
    print("FICTIONAL TEACHING DATA — not real movie reporting")
    print(f"Question: {QUESTION}")
    print("Spoilers excluded; evidence restricted to Orbit Day.")
    for hit in hits:
        print(f"{hit.score:.4f} | [{hit.passage.passage_id}] {hit.passage.text}")


if __name__ == "__main__":
    asyncio.run(main())
