# Catalog Storage and Name Discovery Implementation Plan

> **For agentic workers:** Use executing-plans for inline execution with review checkpoints. Preserve the user's pair-programming workflow; do not delegate or commit without session authorization.

**Goal:** Persist canonical catalog metadata and support external title/actor/director discovery while keeping story/mood recommendations local.

**Architecture:** Introduce a SQLite metadata repository beneath existing catalog routes. Retain the published JSON vector snapshot during migration. Add a separate bounded provider name-search coordinator and contextual ambiguity handling; evidence/content preparation stays separate.

**Tech Stack:** Existing Python/FastAPI/Pydantic/HTTPX/SQLite, React/TypeScript/Zod/TanStack Query and local Ollama.

## Global constraints

- One search bar; story/mood coverage remains the published local catalog.
- Actor credits and Director crew credits are distinct, canonical person IDs are retained.
- No immediate source or LLM preparation required to display external metadata.
- Preserve existing filters, published content, learner modules, model budgets and recoverable errors.
- Never overwrite richer metadata with absent provider fields or silently claim global filtered totals.

## Delivery 1: durable catalog metadata

Files: create backend/src/movie_companion/catalog_store.py and backend/tests/test_catalog_store.py; modify backend/scripts/prepare_semantic_catalog.py and backend/src/movie_companion/main.py.

Interface: CatalogStore.upsert_movie(movie: Movie, fetched_at: str) -> None; CatalogStore.get_movie(movie_id: int) -> Movie | None. Define completeness/source timestamps separately from model publication state.

- [x] Pair exercise: implement retrieval of one validated movie by canonical ID using a parameterised SQLite query. Explain why movie ID is the key and what survives a restart.
- [x] Add meaningful tests for restart persistence, idempotent imports, mismatched IDs, missing fields preserving richer existing data, rollback after failed batch and source timestamps.
- [x] Implement transactional metadata import from read_index(DEFAULT_PATH); keep the JSON file untouched. Begin schema with `movies(movie_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, fetched_at TEXT NOT NULL)` and schema-version migrations.
- [x] Make detail lookup serve valid saved metadata before bounded missing/stale-field hydration. Verify a saved movie opens when TMDB is unavailable.
- [x] Run backend tests and detail-page browser checks; document storage versus vector publication separately.

## Delivery 2: bounded external name search

Files: create backend/src/movie_companion/name_discovery.py and backend/tests/test_name_discovery.py; modify backend/src/movie_companion/tmdb_client.py, schemas.py and main.py.

- [x] Add read-only paged title/person searches and person movie credits using existing provider timeout/concurrency/error policies.
- [x] Assistant completed the exact Director selector and all validation, hydration and persistence at the user’s request; contrast explained in learning note 30.
- [x] Test ambiguous people, misspellings, correct actor/director roles, missing films, duplicate IDs, partial hydration, filter preservation and provider failure with local matches retained.
- [x] Return typed identity candidates and bounded hydrated movie pages. Persist validated metadata through CatalogStore; cap hydration to 20 films per request. Report continuation and incomplete filtering explicitly rather than a misleading global filtered total.
- [x] Verify with mocked provider records first, then credential-safe live title and person smoke checks.

## Delivery 3: one-bar routing and external result UI

Files: modify backend/src/movie_companion/catalog_search.py, frontend/src/components/movie-search.tsx, frontend/src/lib/api.ts and contracts.ts; add frontend/e2e/name-discovery.spec.ts.

- [x] Extend local identity matching to director names. Keep confident identity/typo precedence and unchanged local genre/story routes.
- [x] Add contextual external name-search action for ambiguous unmatched text and broader filmography action for identified people; no permanent category tabs.
- [x] Add person-disambiguation choices, loading/retry and paged tiles with preserved URL/back/filter state.
- [x] Test local story requests make no external discovery calls, explicit name lookup searches TMDB, provider failures retain local results, and external movie details open before AI preparation.
- [x] Run frontend build/browser checks, backend suite and live UI verification; update learning notes with request/response examples.

## Separate subsequent deliveries

Independent content preparation/readiness, source revision storage, parallel research agents and refreshed evidence publication get their own implementation plans after these metadata/name-search slices. User accounts/community/history get separate owner-scoped designs. Derive new semantic vectors in checkpointed background preparation and atomically publish; do not embed external discoveries in the viewing request.

### Pairing checkpoint — 2026-10-10

Write/import setup is complete and separately verified (five tests, 1,500 persisted validated records). Explicit import_catalog_metadata.py copies the existing snapshot; preparation-script and route integration remain pending until the learner completes get_movie. No production route calls the stub. Exercise instructions are in learning note 29.

Lookup and live detail integration complete: 383 backend tests; live saved-response smoke passed. Preparation writes metadata independently before semantic index publication. Frontend contract unchanged; external name discovery is not implemented by this checkpoint.

Name API adapter setup completed and tested offline; live title/person/credit smoke checks succeeded. Director-credit pairing exercise is pending; no live route invokes its stub. Broader search routing and metadata hydration/persistence are still separate pending tasks.


### Completed integration — 2026-10-10

User explicitly asked the assistant to finish operations and include adult movies. Updated title/person/discover requests to include_adult=true, removed adult exclusions from credit selectors and import discovery, and retained nullable strict adult classification in metadata/candidates. No preference filter added. Existing semantic snapshot remains unchanged at 1,500 movies with its original fingerprint; unknown classifications in old records remain unknown.

Delivered bounded name-search coordinator/API, parallel candidate reads, exact acting/directing filmographies, profile-ID validation, up-to-20 hydration, transactional metadata persistence, fresh reuse/stale fallback, partial recovery and page-local filters. Director matching and saved external identity lookup are local; saved external movies don't join semantic search without explicit vector preparation.

Single-bar UI now has contextual external name lookup, distinct same-name profiles, known films, Acting/Directed controls, URL-preserved filters/paging/back navigation and retry without removing collection results. Learning note 30 includes the completed code and end-to-end flow.

Validation: 408 backend cases, 38 browser journeys and production build passed. Live Interstellar search returned 20 hydrated films on page 1 with continuation; Nolan candidate search returned six profiles; person 525 Director credits returned 19 unique films. Live checks added 32 new metadata records, opened saved Insomnia (320), verified local title lookup, and confirmed the semantic snapshot stayed at 1,500. Real UI person selection and Insomnia expanded view/back link verified. Live servers restored.

Initial browser suite found stale count-copy assertions and an actor-search test submitting before state settled. Count assertions now use result/results; the navigation test checks filled input and submitted URL before selecting filters. Draft synchronization now updates during query navigation without a deferred effect that can reset typing. Final suite passed without retries.
