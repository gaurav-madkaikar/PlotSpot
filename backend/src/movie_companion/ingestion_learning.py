"""Learner-owned composition of completed chunking, embeddings and storage."""

import asyncio

import httpx

from .source_sections import source_chunks
from .embedding_learning import embed_texts
from .evidence_store import EvidenceStore, SourceDocument


async def ingest_source(
    client: httpx.AsyncClient, *, store: EvidenceStore, source: SourceDocument,
    model: str, max_chars: int = 600, overlap_chars: int = 100,
) -> str:
    """Return cached if a complete snapshot exists; otherwise index and return indexed.

    Learner slice: cache check → chunks → prefixed batch embedding → save.
    The store and existing helpers own input/output validation. No new clients,
    generated IDs, manual vector parsing, or chat request is needed here.
    """
    snapshot_check = await asyncio.to_thread(store.contains_snapshot,
        source=source,
        model=model,
        max_chars=max_chars,
        overlap_chars=overlap_chars
    )
    if snapshot_check:
        return "cached"
    chunks = source_chunks(
        source,
        max_chars=max_chars,
        overlap_chars=overlap_chars
    )
    embeddings = await embed_texts(
        client=client,
        model=model,
        texts=[f"search_document: {chunk.text}" for chunk in chunks]
    )
    await asyncio.to_thread(store.save_snapshot,
        source=source,
        chunks=chunks,
        vectors=embeddings,
        model=model,
        max_chars=max_chars,
        overlap_chars=overlap_chars
    )
    return "indexed"
