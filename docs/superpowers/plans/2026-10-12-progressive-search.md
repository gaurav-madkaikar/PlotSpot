# Progressive search implementation plan

> Execution: inline implementation, authorized by the user. Preserve the running app, saved content and existing work; no delegation or commits.

**Goal:** Show saved title/description matches before live discovery finishes, reuse prepared search metadata, and defer full movie details to the movie page.

**Architecture:** A local preview request and the existing completed-discovery request run concurrently. Both use one revision-aware prepared catalog; only the completed response owns the pagination snapshot. TMDB search-page metadata supplies new title tiles; missing runtime or person-credit metadata uses a minimal details read.

**Tech stack:** FastAPI/Pydantic/HTTPX/SQLite, React/TanStack Query/Zod, pytest/Playwright.

## Constraints

- Keyword search only; adult films remain available. Filters remain strict.
- Preview responses cannot guess verified person identity or replace completed pagination.
- Query cancellation cannot display older results; external work remains bounded and coalesced.
- SQLite stays authoritative. Cached search metadata must invalidate after writes, including writes from another store instance.
- Search previews cannot falsely mark old full details fresh. Credits, characters and trailers load on the movie page.
- Failed live discovery preserves usable saved matches; an empty incomplete search retains its retry state.

## Task 1: Prepared saved-catalog search

Files: `catalog_search.py`, `search_suggestions.py`, new `catalog_index.py`, `catalog_store.py`, `main.py`, `unified_discovery.py`; tests `test_catalog_index.py`, existing catalog/suggestion tests.

- [x] Add `PreparedCatalog(movies)` with reusable normalized fields, identity fields, word sets, vocabulary and suggestions. Existing `search_catalog(movies, request)` accepts a prepared catalog without changing results.
- [x] Add `SavedCatalogIndex(store).get()` and `.suggest(query)` using a thread lock and a database/WAL file revision. A write during preparation must not label stale data as current. Cache only the current snapshot.
- [x] Reuse compiled suggestion labels until `remember` changes the index; skip similarity comparisons only when an upper bound is below the existing threshold.
- [x] Wire both local and completed search and suggestions to the same saved index. Check cached/uncached equivalence, eviction coverage, same-timestamp writes and shared-store invalidation with pytest.

## Task 2: Lightweight TMDB previews

Files: `name_discovery.py`, `tmdb_client.py`, new `movie_preview.py`, `catalog_store.py`, `unified_discovery.py`; tests `test_movie_preview.py`, `test_tmdb_client.py`, `test_unified_discovery.py`.

- [x] Extend validated title candidates with search-page overview, original title/language, genre IDs and poster path.
- [x] Add `TmdbClient.movie_preview(movie_id, candidate=None, require_runtime=False)`. Use search-page fields when complete; otherwise fetch `/movie/{id}` without appended credits/videos/keywords. Cache and coalesce language/genre configuration reads through a lock.
- [x] Verify IDs and poster paths; retain unknown runtime rather than inventing it. Runtime filters require a real runtime read. Persist previews without deleting richer saved fields or making stale full details fresh.
- [x] Verify no full detail calls for complete title tiles, bounded reads for runtime/person credits, freshness behavior and full details on opening a preview-only movie.

## Task 3: Local results before completed discovery

Files: `main.py`, `unified_discovery.py`, `frontend/src/lib/api.ts`, `frontend/src/components/movie-search.tsx`; tests `test_unified_discovery.py`, new `frontend/e2e/progressive-search.spec.ts` and existing search journeys.

- [x] Add optional `phase=local` to `/api/search/catalog` and the `/api/search/local` alias; default catalog requests remain completed discovery. Local preview withholds actor/director-only matches and selected-person requests until verified.
- [x] Run local and completed queries concurrently on the first page without a snapshot token. Render the completed response when present, otherwise usable local results. Keep the live request cancellation/key semantics intact.
- [x] Display a concise live-discovery indicator; postpone pagination and automatic-correction text until the completed response. Preserve local rows on live errors with a retry control.
- [x] Check a delayed external request, an absent local title, query switching, strict filters, actor verification, failure recovery and stable pagination using isolated browser servers.

## Task 4: Verification and original-checklist audit

Files: learning notes and progress log, original approved design, CI workflow, portfolio documentation.

- [x] Run the backend regression suite, frontend build and focused browser journeys; restart the owned local backend.
- [x] Measure cold local/completed requests and record observed timings with their limits. Verify the feature in the open browser.
- [x] Record the request/data flow and reconcile the original milestones against current code, explicitly marking retired semantic search and deferred drafts.
- [x] Report the completed change and prioritized remaining items; do not claim independent model quality, production load or account isolation from these tests.
