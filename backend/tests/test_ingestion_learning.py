import asyncio
from dataclasses import replace
import json

import httpx

from movie_companion.chunking_learning import chunk_text
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.ingestion_learning import ingest_source


SOURCE = SourceDocument("fixture", 101, "Fictional recycled fabric suits were silver.", "Authored fixture", "fixture://test", "v1", "safe")
SETTINGS = {"model": "test-model", "max_chars": 30, "overlap_chars": 5}


def test_indexes_then_reuses_snapshot_without_document_http(tmp_path):
    requests = []
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["model"] == SETTINGS["model"]
        chunks = chunk_text(SOURCE.text, max_chars=30, overlap_chars=5)
        assert body["input"] == [f"search_document: {chunk.text}" for chunk in chunks]
        requests.append(body)
        return httpx.Response(200, json={"embeddings": [[1.0, 0.5] for _ in body["input"]]})
    async def run():
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)) as client:
            assert await ingest_source(client, store=EvidenceStore(tmp_path), source=SOURCE, **SETTINGS) == "indexed"
            assert await ingest_source(client, store=EvidenceStore(tmp_path), source=SOURCE, **SETTINGS) == "cached"
    asyncio.run(run())
    assert len(requests) == 1


def test_changed_source_calls_embeddings_again(tmp_path):
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"embeddings": [[1.0, 0.5] for _ in body["input"]]})
    async def run():
        store = EvidenceStore(tmp_path)
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)) as client:
            await ingest_source(client, store=store, source=SOURCE, **SETTINGS)
            result = await ingest_source(client, store=store, source=replace(SOURCE, revision="v2", text=SOURCE.text + " Updated."), **SETTINGS)
            assert result == "indexed"
    asyncio.run(run())
    assert len(requests) == 2
