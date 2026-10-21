# Persistent Evidence Pairing Plan

**Goal:** Reuse document embeddings across process runs while preserving source revision and model/chunking identity.

**Architecture:** Chroma PersistentClient stores explicit locally computed vectors, text and metadata. Snapshot fingerprints cover the full source record, embedding model tag, document-prefix version, and chunk settings. Retain immutable revision snapshots; callers explicitly load one fingerprint, not all historical records. Model-separated collections prevent mixed dimensional spaces. A learner-owned ingestion helper composes cache check, chunking, embedding and save; query embeddings remain per query.

**Tech Stack:** Python 3.12, HTTPX, pytest, local Ollama and Chroma 1.x. No cloud account, default embedding model, or additional model download.

## Constraints

Teaching-only, single-writer local storage; no public API, accounts, private data or real articles. At most 200 chunks per source. Unknown spoiler labels remain unknown. Never claim a cache hit for an incomplete snapshot. Preserve source offsets and provenance. Cache keys pin tags, not model weight digests, a documented limitation. Old snapshots remain retained and storage cleanup is future work.

## Task 1 — assistant-owned persistence

- [ ] Add Chroma dependency and lock it. Verify PersistentClient, explicit embeddings and metadata APIs from official documentation.
- [ ] Create `evidence_store.py`: validated SourceDocument, stable snapshot fingerprint, bounded save/load and complete-snapshot cache check. Use embedding_function=None and explicitly supplied embeddings so Chroma never downloads its default embedding model.
- [ ] Add real temporary-directory tests for reopen, cache invalidation, source/movie/spoiler provenance, incomplete snapshot detection, and vector validation.

## Task 2 — learner ingestion composition

- [ ] Create `ingestion_learning.py` with unfinished `ingest_source(client, *, store, source, model, max_chars, overlap_chars) -> str`. Return cached/indexed; core learner logic uses contains_snapshot, chunk_text, embed_texts and save_snapshot. Assistant owns validation at the boundary and tests with mocked local inference.
- [ ] Provide a fictional persistent RAG script. After learner implementation, its first run embeds source chunks; a second process reuses them, embeds the question, retrieves via the learner's exact cosine ranker, then generates a cited answer.
- [ ] Explain Chroma collections/records, cache identity/invalidation, sync storage versus async HTTP, snapshot consistency and limits in lesson 13. Verify assistant tests and prior suite independently of the unfinished learner helper. Do not implement the helper or claim a real persistent RAG run before review.
