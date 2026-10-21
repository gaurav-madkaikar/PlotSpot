# Lesson 13 — reuse document embeddings across runs

## What changes now?

Your previous scripts embedded document text on every run. Now Chroma stores the passage text, numeric vector, and source metadata on disk. The next process can load those records without embedding the unchanged source again. Ollama still embeds a new question and generates its answer.

We installed Chroma 1.5.9, locked in `backend/uv.lock`. This uses a local `PersistentClient`, not a cloud account. Chroma persists at the specified path and loads it when reopened; see the [official client documentation](https://docs.trychroma.com/docs/run-chroma/clients). We pass vectors explicitly and set the collection's `embedding_function=None`: the default embedding model is not used or downloaded. Chroma supports storing supplied vectors alongside text as described in [Adding Data](https://docs.trychroma.com/docs/collections/add-data).

```text
Source record → complete matching snapshot exists?
                 ├─ yes: return "cached", skip document inference
                 └─ no: chunk → embed document chunks → save → return "indexed"

Question → query embedding
Saved snapshot → load passages → your cosine ranking → grounded generation
```

This is source-embedding reuse, not an answer cache. The teaching script has no query or generated-answer cache. The webpage's frontend query cache and the backend TMDB cache are separate systems from this persistent evidence store.

## What is a Chroma collection?

A collection contains records with unique IDs, document text, embeddings, and metadata. Our wrapper puts different embedding model tags in different collections so their vector dimensions/spaces are not mixed. The collection name is derived from a model-tag hash; it does not contain the full source text.

The current teaching adapter uses Chroma `.get()` to load one bounded source snapshot, then retains your exact cosine ranker. `.get()` does not perform similarity ranking. Chroma also has `.query()` for indexed similarity search; we will evaluate that larger-corpus path later. See the [official Query/Get distinction](https://docs.trychroma.com/docs/querying-collections/query-and-get). Do not describe this exercise as approximate-nearest-neighbor retrieval yet.

## Source records and snapshots

`SourceDocument` is a validated dataclass containing source ID, movie ID, text, source label/reference, revision, and spoiler status. `source_ref` is an attribution reference, not something this helper fetches. The demo uses `fixture://orbit-production` because its article is authored fictional data.

The snapshot key is a SHA-256 fingerprint of:

- The complete source record, including text, identity, revision and spoiler label.
- The embedding model tag and document prefix.
- The chunker version, window size and overlap.

Changing any of those produces a different key. Thus an edited source cannot accidentally reuse its older text's embeddings. A hash identifies the configuration/content; it does not judge source trust or factual accuracy.

The assistant checks that every expected chunk exists with matching text, source offsets, metadata and valid vectors. A partly written or damaged snapshot is not a cache hit. Old snapshots remain retained and are loaded only when explicitly requested by their matching source/configuration; the demo never mixes all historical versions into retrieval.

The model tag is not a weight digest. Replacing local model weights under the same tag could reuse incompatible embeddings; we will pin model identity for stronger indexing later. Likewise, this store is a single-writer teaching component, with no cleanup policy, account permissions or transactional multi-source ingestion. Published/fetched dates and richer source connectors are subsequent production metadata. Current sources are authored public fixtures, not private conversations.

## Your coding slice

Implement only `ingest_source` in `backend/src/movie_companion/ingestion_learning.py`.

1. Call `store.contains_snapshot(source, model=model, max_chars=max_chars, overlap_chars=overlap_chars)`. If true, return the exact string `"cached"` without an embedding request.
2. Otherwise, call your `chunk_text` helper on `source.text` with the same settings.
3. Build a list containing `search_document: ` followed by each chunk's text. These prefixes are for our Nomic model; they are not universal embedding rules.
4. Await your `embed_texts` helper, passing the supplied client, model, and text list.
5. Call `store.save_snapshot(source, chunks, vectors, model=model, max_chars=max_chars, overlap_chars=overlap_chars)`, then return `"indexed"`.

The store owns input validation, chunk/vector correspondence, snapshot IDs, and metadata. Keep using the existing helpers; no manual HTTP parsing, new client, generated source IDs, or chat call belongs in this function.

This is the first exercise where you compose several of your completed AI helpers. The prefix list must preserve chunk order so each returned vector attaches to the right source span.

## Synchronous versus asynchronous calls

`store.contains_snapshot`, `chunk_text`, and `store.save_snapshot` are ordinary synchronous calls. `embed_texts` is an asynchronous HTTP call, so it needs `await`. Making `ingest_source` async does not make every operation inside it asynchronous.

This bounded CLI lesson performs synchronous local storage work directly. Before integrating storage into FastAPI's request path, the assistant will handle scheduling/thread boundaries so disk work does not block concurrent requests.

## Test and run

From `backend`:

```sh
.venv/bin/pytest tests/test_ingestion_learning.py -q
```

Two learner tests intentionally fail against the starter. They check a first embedding request followed by a cache hit, and re-embedding when the source changes. They use mock HTTP responses and real temporary local storage, with no Ollama call. Storage tests separately exercise cache invalidation, partial snapshots, metadata, vectors and reopening from another Python process.

Preparation verified: all 172 implemented backend checks pass, including 17 storage cases; the two learner tests fail as expected. New Python files compile. The full suite includes the unfinished exercise, so it is intentionally red until the helper is completed.

Once implemented, with the existing local models running:

```sh
.venv/bin/python scripts/try_persistent_rag.py
.venv/bin/python scripts/try_persistent_rag.py
```

For a fresh demo database, expect document ingestion `indexed` on the first invocation, then `cached` on the second. Existing matching data can make the first invocation cached too. The script still embeds the question and calls the chat model on both runs. Inspect the actual outputs; they have not been run through the unfinished helper yet.

Demo data lives in the project's ignored `data/chroma/learning` directory. Avoid deleting it to test invalidation: change a source revision or settings instead, and observe a new snapshot. Tests use isolated temporary directories and do not touch this demo path.

## Concepts to explain afterwards

1. Why are document embeddings reused but query embeddings still requested?
2. Why must chunk settings and model identity be part of the cache key?
3. Why does merely finding one stored chunk not prove a snapshot is complete?
4. Why preserve source revision and offsets alongside the text?
5. What changes when using Chroma's indexed query rather than loading vectors for our ranker?

We will save the review answers and real two-run results after your implementation. No persistent-RAG answer or performance gain is claimed at preparation.

## Completed ingestion review — 2026-10-10

The learner connected the cache check, chunker, prefixed batch embedding and snapshot save. The assistant fixed one remaining keyword mismatch: `save_snapshot` expects `vectors=embeddings`, not `embeddings=embeddings`. The left side is the receiving method's parameter name; the right side is the local variable holding the vector list. All 174 backend tests pass.

The assistant ran the persistent demo twice in separate processes against local Ollama:

| Run | Document ingestion | Generated result |
|---|---|---|
| First | `indexed` | `The suits in Orbit Day were made from recycled fabric and painted silver.` with source chunk citation |
| Second | `cached` | `insufficient_evidence`, with the fixed abstention explanation |

The second process confirmed document reuse, but its answer abstained despite the authored source containing material and colour. Preserve this failure: cached evidence does not guarantee consistent model answers. Both invocations still embedded the question and called the chat model. No answer-quality or latency improvement is claimed from these two runs. Source storage, retrieval and generation are separate boundaries and need separate checks; live answer behavior remains an evaluation concern.

## Answers to the review questions

1. **Why reuse documents but embed the question?** The indexed source and its configuration have not changed, so their vectors remain reusable. A new question needs a representation in the same embedding space to compare with them. We have not implemented a query-vector cache.
2. **Why include model and chunk settings?** Changing the text windows or embedding model changes what each vector represents. Reusing vectors under a different policy/model could attach the wrong representation to a chunk or compare incompatible spaces. Model weight digests still need pinning beyond tags.
3. **Why isn't one chunk enough?** A write may be interrupted or records may be missing. A cache hit must verify the full expected set, original source slices, metadata and vectors; otherwise some relevant evidence could silently disappear.
4. **Why revision and offsets?** They locate the chunk in a particular version of the source and support inspection of its attribution. Offsets alone cannot identify which text version they describe.
5. **What changes with indexed query?** Chroma can retrieve nearest candidates from its index instead of loading every vector for exact Python ranking. We must compare recall/latency, retain source/movie/spoiler filters, and understand distance versus similarity conventions. In this small lesson, Chroma provides persistence and your ranker still selects evidence.

## First implementation review — 2026-10-10

The cache check and chunking call are correct. The suite has 172 passing cases and two failing ingestion cases. The first runtime failure is a missing `client` argument to `embed_texts`. Two additional issues are visible in the code: chunk text lacks the Nomic `search_document: ` prefix, and `EvidenceStore` has no `save_chunk` method. Use the complete `save_snapshot` batch method with source, chunks, embeddings, model and the same chunk settings. The learner implementation was left unchanged for this focused composition correction. No real persistent example was run through the failing helper.
