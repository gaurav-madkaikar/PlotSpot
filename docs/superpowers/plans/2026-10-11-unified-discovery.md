# Unified movie discovery implementation plan

User-approved continuation of the search architecture in `docs/architecture/production-guidelines.md`. Implement in the shared checkout; preserve existing work and saved content.

**Goal:** One automatically updated, paginated grid combines saved keyword matches with verified TMDB title/person results.

**Architecture:** Keep deterministic ranking in `catalog_search.py`. Add a `UnifiedDiscovery` service owning bounded external discovery, hydration, persistence, request coalescing and five-minute result snapshots. Additive response fields describe partial coverage, person choices and a pagination token. Demo browsing remains offline. Description keywords remain local; search does not call an LLM.

**Constraints:** Retain adult films. No separate results panel or search-mode chooser. Use exact Director crew roles. No automatic person choice if identities are ambiguous. Cache at most 64 snapshots; allow two discovery builds concurrently, provider HTTP concurrency remains four. Fetch at most two title pages and hydrate at most 60 new candidates per query, with a 20-second external-work deadline. Include all already-saved verified person credits. Counts describe the deduplicated discovered pool, never TMDB's global total. Expired/mismatched pagination tokens restart at page one. Provider failure retains completed/local matches with a retry action; partial page-one searches are not reused on retry.

- [x] Backend: expose complete local matches without changing public pagination; add response fields with defaults. Implement service and API wiring/shutdown. Test out-of-catalog films, credits, ambiguity, deduplication, filters, adult retention, bounds, stale fallback, timeouts, coalescing, cache expiry and pagination.
- [x] Frontend: retire the separate name panel; add compact person clarification and partial-search recovery above the existing grid. Keep debounce, composition support and filters. Carry snapshot token on page navigation, reset on query/filter/person changes. Validate through Zod.
- [x] Verify: backend suite, frontend build and focused browser journeys on isolated ports. Restart the live backend and check a real outside-catalog title and actor/director queries. Document limits and learning flow in lesson 55.

Alternatives considered: local-only fallback misses external exact matches whenever local matches exist; appending provider pages to mutable local pages causes duplicate/moving results. A bounded, cached merged pool is the chosen first step. Distributed/shared snapshots and full-provider filmography traversal are later deployment work.
