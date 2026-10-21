# 22 — Finding films by meaning

## Try it live

On Discover, choose **Mood or story**. Enter “a thoughtful science fiction story about communicating with aliens” and choose **Find my film**. Arrival should rank near the top. Set a runtime or language filter and compare the results. Only ten films are currently indexed; title/cast search still uses the broader live TMDB provider.

## How your code becomes a feature

1. `backend/scripts/prepare_semantic_catalog.py` fetches the ten canonical movie IDs from TMDB. Each response becomes the existing validated `Movie` object: title, synopsis, genres, director, cast, language, runtime and poster URL.
2. `semantic_catalog.document_text(movie)` builds a short searchable description. It does not use scripts or discussion evidence. TMDB synopses may still reveal a premise; this is not a guarantee of spoiler-free metadata.
3. Your `embedding_learning.embed_texts()` sends one batch to Ollama `/api/embed`: `{model: "nomic-embed-text:v1.5", input: ["search_document: ...", ...], truncate: false}`. Ollama returned ten vectors of 768 numbers.
4. `save_index()` writes metadata, vectors, model tag, preparation time and a fingerprint to `data/private/semantic-catalog.json`. A temporary file is renamed only after validation. Failed preparation leaves the published file intact.
5. The browser submits `POST /api/discover` with `{query, genre, language, max_runtime}`. `main.py` validates it and calls `SemanticSearch.search()`.
6. The backend reads and validates the index. It removes movies that violate the requested filters before ranking. A missing runtime cannot satisfy a runtime limit. If nothing is eligible, there is no model call.
7. Your embedding function embeds `search_query: <description>`. Your `vector_math.cosine_similarity()` compares this vector with each eligible movie vector. The six highest scores become normal movie tiles. Clicking a tile opens the existing movie page.

Example: a space-family query might rank Interstellar first, but a 120-minute limit removes it before ranking. The model cannot override that constraint or invent a new movie ID.

## Where the caches live

**Persistent movie index:** the JSON file survives backend restarts. Browsing never rebuilds it. Explicit preparation fetches current metadata; matching fingerprints skip embedding calls. `--refresh` explicitly replaces it. This small exact-search index is separate from the existing Chroma evidence store. Ten vectors do not need an approximate nearest-neighbor database; larger catalogs can use a dedicated catalog collection later.

**Backend query-vector cache:** `SemanticSearch.cache` is an OrderedDict with at most 64 entries and five-minute expiry. It stores only the query vector. Changing filters reuses that vector, then filters/ranks again. Same-query requests in flight share one task, even if one viewer disconnects. A failed embedding is not cached. This is not conversation memory or long-term preference storage.

**Frontend result cache:** React Query uses `['semantic-discovery', body]` as its key. The complete request, including filters, distinguishes results. Responses remain fresh for five minutes. A model request is triggered on submit or an example click, not each keystroke. After a submitted query, changing a filter requests the corresponding constrained results.

## Common questions, answered

**Is this an LLM generating recommendations?** It uses an embedding model, not a chat model. It ranks known records. It does not generate movie titles or explanations.

**Is this RAG?** This feature is semantic retrieval. RAG adds generation from retrieved evidence; the Discuss feature does that. Keeping them separate makes it easier to measure the retriever without chat-model noise.

**Does 0.8 similarity mean an 80% chance I will enjoy it?** No. Cosine similarity is a ranking signal, not a calibrated probability. The UI does not show confidence percentages. Even an unrelated query has a nearest neighbor; results are labelled suggestions, not guaranteed matches.

**Why not ask the model to obey filters?** Runtime, language and genre have precise metadata values. Deterministic checks are reliable and testable. Natural-language constraints should be selected with the filters; we have not implemented an intent-parsing agent yet.

**What prevents malicious actions?** This path has no chat agent, shell, browser navigation or write tools. Query text is only embedded. Only reviewed catalog IDs can enter the saved index. The model endpoint is fixed to local Ollama, work is bounded, malformed vectors fail validation, and caller errors do not expose provider details. This limited capability is a stronger boundary than telling a model to behave.

**What did the evaluation compare?** Ten manually labelled development queries identify an expected movie. The runner checks whether that ID is first or within the first three results, and whether every result obeys filters. Similarity thresholds are not the labels. Literal title/cast substring search is a deliberately simple baseline.

**What were the real results?** With TMDB metadata and local nomic-embed-text:v1.5, the expected movie ranked first for 8/10 queries and within the top three for 10/10. Literal title/cast substring search found none of these descriptive queries. This tiny development set is not held-out and constrained cases are easier. Do not claim general recommendation accuracy or compare against a strong hybrid baseline from these results.

## Reproduce from the project root

```sh
backend/.venv/bin/python backend/scripts/prepare_semantic_catalog.py
backend/.venv/bin/python backend/scripts/evaluate_discovery.py
```

Use `--demo --path .cache/demo-catalog.json` to explicitly prepare authored demo metadata instead of TMDB. Use `--refresh` to replace a published index after metadata changes. Live preparation needs the existing local TMDB token and Ollama embedding model; do not paste credentials into code or chat.

## Remaining work

Expand beyond ten films, add held-out and out-of-catalog queries, compare lexical/BM25/hybrid baselines, then build parallel recommendation/evidence orchestration. This delivery is retrieval infrastructure, not a completed multi-agent system.
