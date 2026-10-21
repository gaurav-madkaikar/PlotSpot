"""Fictional persistent RAG demo; run twice after completing ingest_source."""

import asyncio
from pathlib import Path

import httpx

from movie_companion.embedding_learning import embed_texts
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.grounding_learning import answer_from_hits
from movie_companion.ingestion_learning import ingest_source
from movie_companion.retrieval_learning import retrieve_passages
from try_chunking import ARTICLE


ROOT = Path(__file__).resolve().parents[2]
MODEL = "nomic-embed-text:v1.5"
SOURCE = SourceDocument(
    source_id="orbit-production", movie_id=900000001, text=ARTICLE,
    source_label="Authored fictional production programme",
    source_ref="fixture://orbit-production", revision="v1", spoiler_status="safe",
)
SETTINGS = {"model": MODEL, "max_chars": 180, "overlap_chars": 60}
QUESTION = "What material and colour were used for the suits in Orbit Day?"


async def main():
    store = EvidenceStore(ROOT / "data/chroma/learning")
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        outcome = await ingest_source(client, store=store, source=SOURCE, **SETTINGS)
        print(f"FICTIONAL TEACHING DATA — document ingestion: {outcome}", flush=True)
        passages = store.load_snapshot(SOURCE, **SETTINGS)
        query = (await embed_texts(client, model=MODEL, texts=[f"search_query: {QUESTION}"]))[0]
        hits = retrieve_passages(query, passages, query_model=MODEL, movie_id=SOURCE.movie_id, k=2)
        result = await answer_from_hits(client, model="llama3.2:3b", question=QUESTION, hits=hits)
    print(f"Question: {QUESTION}\nStatus: {result.status}\nAnswer: {result.answer}")
    for hit in hits:
        if hit.passage.passage_id in result.citation_ids:
            print(f"[{hit.passage.passage_id}] {hit.passage.text}")


if __name__ == "__main__":
    asyncio.run(main())
