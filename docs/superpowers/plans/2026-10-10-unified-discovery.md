# Unified movie discovery implementation plan

Approved user scope: one search bar, 200 stored movie records, on-demand detail/evidence, backend pagination and honest genre/unsupported results.

Architecture: retain the legacy search API for existing callers; the main UI uses the separate /api/search/catalog endpoint. A provider-validated 200-film metadata snapshot is prepared explicitly and atomically. Exact/prefix title and cast matches and conservative typo corrections precede genre and synopsis-supported semantic ranking. Genre constraints are deterministic and pagination follows filtering/ranking. Local demo mode stays fixture-backed. Scripts/evidence remain isolated.

Constraints: local Ollama only; reuse learner embedding/cosine functions; preserve authored exercises and saved quiz/fact content; no new paid services; light editorial UI; no commits requested. A larger catalog is not proof of semantic relevance.

- [x] Add query interpretation and unified catalog search modules, request/result pagination contracts and routes. Test exact title/cast/typo, romance, explicit negation, contradictory filters, unsupported descriptions, non-overlapping pages and no model calls for deterministic routes.
- [x] Extend explicit catalog preparation to collect canonical TMDB IDs from genre-balanced discovery pages; fetch lightweight movie metadata with six main cast names, validate IDs, reuse unchanged embeddings, batch new embeddings and publish 200 records atomically. Do not fetch scripts/RAG/content banks.
- [x] Replace mode selector with one Find your next film searchbox, Title, actor, genre, or mood… placeholder, existing filters, suggestions and Previous/Next pagination. Preserve URLs/back navigation and migrate mode=meaning URLs without losing q.
- [x] Run deterministic backend/build/browser checks, prepare real 200-film catalog and run labelled exact/genre/negative/semantic evaluation. Inspect live romance and pagination, save a learning note and restore app servers.

Implementation interfaces: `CatalogQuery(query, genre, language, max_runtime, page, page_size)`; `search_catalog(service, request, demo=False) -> MovieSearchResponse`; `SemanticSearch.query_vector(query, dimension) -> vector` reuses existing bounded cache/task sharing. The saved catalog is the source of valid result IDs; its identity manifest replaces the original ten-ID-only constraint. Preparation obtains that manifest solely from validated fixed TMDB API responses.

Completed validation: 328 backend tests, 32 browser tests, build and diff checks passed. Saved 200 TMDB records with 768-dimensional nomic vectors. Actual romance returns 20 genre-tagged films. Live pages 1/2 each return 20 records with no overlap. Evaluation reports and screenshot are under evals/discovery and .cache/previews. Descriptive ranking misses and English/main-cast limits are documented, not hidden. No source/content banks were replaced.
