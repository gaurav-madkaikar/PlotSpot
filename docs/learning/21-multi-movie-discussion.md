# 21 — One RAG pipeline, ten movies

Discuss now supports Inception, Interstellar, Arrival, The Matrix, Knives Out, Parasite, Spirited Away, The Truman Show, The Grand Budapest Hotel and Dune (2021). Each uses the learner pipeline you already wrote. We extended the inputs and application wiring, without adding another AI framework.

Quiz and Facts still require prepared collections. Interstellar retains six facts and fourteen scored questions plus one reflection; other films disclose that those collections are not prepared yet.

## Follow the request

`Movie page ID → feature inventory → reviewed article mapping → revisioned source → movie-scoped Chroma passages → your query embedding/ranking/grounded generation → cited answer`

`wikipedia_source.py:MOVIE_ARTICLES` maps canonical TMDB IDs to exact Wikipedia titles. For example, 329865 maps to Arrival (film), while 496243 maps to Parasite (2019 film). The model does not select an article URL. The existing source helper checks the returned title, page ID, revision and text bounds.

The first real check found four articles exceeding the 100,000-character text bound. Extraction now stops at reference/notes/navigation headings rather than increasing that limit or cutting a paragraph. Movie-body section spans remain intact. The extraction revision now ends with `sections-v3-body`, so the persistent store creates distinct vector snapshots for the new representation.

All ten mapped articles passed actual API checks; their retained text ranges from about 24,000 to 65,000 characters. This verifies current source availability and parsing, not that every future question is answerable.

## Feature inventory

A read-only GET to `/api/movies/329865/features` returns:

```json
{"movie_id":329865,"discussion":true,"quiz":false,"facts":false}
```

Discussion means a reviewed mapping exists. It does not guarantee that Wikipedia/Ollama is healthy at that moment. Quiz/Facts mean a validated SQLite collection exists. Inventory calls do not fetch Wikipedia, prepare sources or call the model. They expose no story text and may run before spoiler consent.

React Query fetches inventory separately from movie metadata, with a 30-second freshness period. Zod validates it; the API client additionally checks that the returned movie ID matches the page. Failed inventory leaves the poster/details visible and provides Retry features. Panels receive explicit availability instead of checking whether the ID equals Interstellar's ID.

## Caches and isolation

The backend source cache holds separate entries:

```text
329865 → (expiry, Arrival source)
157336 → (expiry, Interstellar source)
```

It has at most ten entries, a five-minute expiry and no generated answers. Returning to a movie can reuse its source; expiry refreshes only that movie. Restarting clears this memory cache.

Chroma is persistent. Its snapshot identity contains movie ID, source revision, extraction/chunk settings and embedding model. Changing any of those requires a different snapshot. Source caching and vector reuse therefore solve different problems.

The service checks coverage and spoiler consent before source/model I/O. It verifies the source movie ID, loads that source snapshot and filters eligible passages to the requested movie. Your retrieval wrapper scopes passages again. Citation IDs are independently checked before returning the answer.

Changing movie or revoking spoilers remounts the panel, clears incompatible output and aborts its browser request. A browser abort does not guarantee an already-running model has stopped; server deadlines and the shared single model slot still matter.

## Actual local-model results

Using llama3.2:3b and nomic-embed-text:v1.5:

- Who directed Arrival? → Denis Villeneuve, with an Arrival article citation; 6.47 seconds.
- Who directed The Truman Show? → Peter Weir, with a Truman Show article citation; 3.45 seconds.

These times include initial vector ingestion and answering, but exclude source fetching because the verified source snapshots were supplied to the service cache. Both used the real service and persistent application store. Two easy questions are smoke checks, not a broad accuracy benchmark.

Reports: `evals/movie-rag/movie-coverage-smoke.json` and `multi-movie-ollama-smoke.json`.

## Questions and answers

**Why use mappings instead of searching Wikipedia automatically?** Titles can collide across remakes and years. Reviewed ID-to-title mappings establish an identity baseline before autonomous discovery.

**Why not enable Quiz/Facts whenever Discuss works?** Finding evidence differs from publishing validated collections. Quiz uniqueness/distractors and fact support still need preparation and review.

**Where is RAG?** Your question is embedded, scoped passages are ranked, and retrieved evidence is supplied to Ollama. Inventory and metadata calls are ordinary backend work.

**Do different films need separate models?** No. They use the same model and different scoped evidence.

**What do the tests check?** Consent before I/O, wrong-movie passage exclusion, per-movie citations, cache reuse/expiry, inventory errors, reference removal, another film's questions and inventory-driven panel display. Browser fixtures mock inventory independently of private local SQLite data, so tests work on a fresh checkout.

**What remains?** Semantic recommendations, more prepared collections, parallel research/story orchestration, community/preferences and consolidated held-out evaluation/CI. These should be separate working slices.

Verification: 289 backend tests, 27 browser checks and frontend build passed.
