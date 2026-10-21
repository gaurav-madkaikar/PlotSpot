# 55. Searching beyond the saved catalog

Previously, the main search only read SQLite. Live discovery existed separately. Now a single search request combines both sources and returns one grid.

## Follow one request

Imagine typing **Hundreds of Beavers**. After a 350 ms pause:

1. `frontend/src/components/movie-search.tsx` puts the query in the URL. React Query calls `searchMovies` from `frontend/src/lib/api.ts`; Zod validates the response in `contracts.ts`.
2. `/api/search/catalog` in `backend/src/movie_companion/main.py` builds a validated `CatalogQuery`. Demo mode remains offline. Live queries of at most 120 characters enter `UnifiedDiscovery.search`.
3. `unified_discovery.py` loads a snapshot of saved metadata. `catalog_search.py` ranks title, cast, director and literal description matches, including conservative spelling corrections.
4. TMDB title search and person search run concurrently. `asyncio.gather(..., return_exceptions=True)` lets one branch fail while the other remains useful. An unambiguous exact person can be selected automatically; shared names can be resolved through the unified **Did you mean?** suggestions.
5. Selected people use `/person/{id}/movie_credits`. Actor matches come from `cast`; director matches require the exact `Director` crew job. A producer or cinematographer is not treated as a director. Verified IDs also find cameos missing from the top-cast preview.
6. Fresh saved records are reused. New/stale candidates use `TmdbClient.movie(..., enrich=True)` to obtain validated metadata. Newly fetched records persist in SQLite. Failed refreshes can retain old records without falsely resetting their freshness dates.
7. Local and discovered movies merge in a dictionary keyed by TMDB ID. Filters apply to both. Rank first, deduplicate, freeze the resulting list, then take the requested page.
8. The response includes an opaque `search_token`. Next/Previous carry this token so another search growing the catalog cannot move films between these pages.

The live check returned the previously absent **Hundreds of Beavers** (ID 1019939) in approximately 1.35 seconds. That is one development observation, not a latency guarantee. See `evals/search/unified-live-v1.json`.

## Why do we need another cache?

These layers have different jobs:

| Layer | Holds | Lifetime / role |
|---|---|---|
| React Query | Parsed API responses keyed by query, filters, person and page/token | Five-minute search freshness; UI navigation and request cancellation |
| UnifiedDiscovery | Complete ordered result pools and active tasks | Five minutes, at most 64 pools; stable pages and shared concurrent searches |
| TmdbClient | Raw validated provider response payloads keyed by endpoint/parameters | Ten minutes, 256 entries; avoids repeated upstream calls |
| SQLite | Movie metadata and its fetch timestamp | Survives restarts; search hydration currently treats metadata as fresh for seven days |

A cache is temporary; SQLite is persistent storage. These in-memory caches belong to one backend process. A multi-instance deployment needs shared snapshots/admission or routing that preserves ownership. An old token after restart/expiry restarts at page one. It is not an authorization token and contains no credentials.

## What does coalescing mean?

If two users request the same query and filters simultaneously, `pending[key]` holds one running task. Both await it. `asyncio.shield(task)` means one browser cancelling its request does not cancel shared work needed by the other browser. Shutdown explicitly cancels and joins all owned tasks.

Two distinct external builds can run at once; additional builds return local results marked partial rather than joining an unlimited provider queue. Within those builds, TMDB limits HTTP concurrency to four. This admission control is not a production load-test result.

## What happens when something fails?

A partial response is still HTTP 200 with usable movies and `partial: true`. The UI shows available movies without a warning banner. If there are no movies to show and the search failed, it displays **Search couldn’t be completed** with **Try again**, rather than claiming no matches exist. Partial first-page responses are not reused on retry; later pages can still reuse their token for consistent navigation.

The 20-second external deadline cancels and joins unfinished hydration tasks, preserves completed movies, and returns partial results. SQLite failures remain retryable service errors. Invalid or mismatched movie identities are withheld, never saved.

Person names are not IDs. TMDB returned multiple identities named Christopher Nolan and Amy Adams in the live check. After choosing Christopher Nolan (ID 525) through a suggestion, directed-film results include Inception, Interstellar and The Dark Knight, with exact credit membership. Selecting an identity excludes other people who share its name. Unknown/unselected names can still show local string matches while asking for clarification.

A valid external exact title also overrides a local spelling guess. A smaller local catalog must not silently rename a real movie merely because it knows a similar title.

## Scope and limits

- This is keyword/name search, with spelling support. It does not use embeddings or an LLM.
- Description keywords search saved descriptions. TMDB contributes title/name search; this is not global description search.
- A build fetches at most two title pages and hydrates at most 60 candidate IDs. All already-saved verified person credits can be included beyond this hydration bound. Very broad titles/filmographies may remain incomplete; `limited` reports these bounds in the API. `total` counts the deduplicated pool, not the entire TMDB catalog.
- Hydration currently fetches enriched metadata to apply runtime/language filters and preserve search fields. Lightweight preview ingestion with independent field freshness is a further optimization.
- Adult films remain included. Preference-based filtering is future work.
- Finding a movie does not fetch scripts, invoke Ollama, generate facts/quizzes, or imply that movie has prepared content. Those workflows remain separate.
- Search calls consult the provider even when local matches exist, unless a complete query snapshot is cached. Requests over the provider's existing 120-character bound use local search only.

## Concepts and answers

**Why not concatenate page one from each source?** Their ordering and duplicates differ. Filtering or dropping duplicates afterward can shrink pages or omit movies. We merge a bounded full candidate pool and paginate once.

**Why use an ID-keyed dictionary?** Two sources can return the same film or its translated title. Its TMDB ID is the stable identity. Different remakes sharing a title retain different IDs.

**Why not let the LLM choose the person or fix every typo?** Metadata provides verifiable identities. Ambiguous choices need clarification; a guessed identity would silently mix filmographies. Deterministic correction plus exact external evidence is easier to inspect and test.

**Are these checks evaluations?** They verify search behavior against known scenarios: ID membership, duplicate removal, strict filters, recovery and stable pages. They are different from assessing factual LLM answers. The five-query live report is a smoke check, not an independent relevance benchmark or production performance evaluation.

**What should we measure later?** Label a held-out set of title/person/typo/description queries and expected relevant IDs; report recall/precision at K, person ambiguity behavior, provider-failure coverage, p95 latency and upstream request counts. Keep broad-coverage bounds explicit.

References: [TMDB title search](https://developer.themoviedb.org/reference/search-movie), [person movie credits](https://developer.themoviedb.org/reference/person-movie-credits).

## UI refinement: one suggestion block

`frontend/src/lib/search-suggestion-options.ts` combines saved spelling corrections (movies/actors/directors) with relevant provider people. Specific TMDB identities replace duplicate generic same-name suggestions. A known film distinguishes two people with the same name; selecting that suggestion updates the query and retains the verified person ID internally. Filters survive and pagination resets.

The UI no longer has **Which person did you mean?**, a selected-person banner or **Acting / Directed** controls. Person discovery still runs internally so actor/director searches can find movies outside the saved catalog. A title query does not automatically produce visible person choices: unrelated provider name fragments are filtered out of suggestions.

Live example: `sydney sweene` produces Sydney Sweeney suggestions distinguished by Anyone but You / Yield. Selecting Anyone but You resolves person ID 115440, updates the field to Sydney Sweeney and shows her films in the same grid. This is a spelling/identity check, not a claim that all future names are resolved correctly. Browser coverage checks this flow, Batman without irrelevant people, mixed movie/actor/director suggestions, duplicate removal, mobile layout, filters and stable pages.

## Exact titles, completions and cache eviction

The provider's suggestion index is a 1,500-record LRU working cache. Once more movies were saved, that cache could evict Interstellar even though SQLite still contained it. This made exact-title suppression fail and removed its spelling suggestions. The live suggestion endpoint now reads the full saved metadata corpus in a worker thread and creates an index large enough for that snapshot. Newly saved movies are included on the next request. This scan suits the current catalog; a much larger deployment would need an indexed suggestion query or a versioned snapshot rather than repeated full scans.

`identity_sort_key` is shared by local search and the merged provider results. Exact identities keep their priority. For partial titles, a completion at the start of the canonical title outranks incidental words and aliases; shorter completions rank first. Thus `Interstell` finds Interstellar before Interstellar Wars or Container Interstellar. Filters still apply and browsing remains alphabetical.

The frontend also suppresses suggestions when the returned movie titles contain the exact normalized query, protecting against a stale suggestion response. The close button dismisses suggestions for the current query: changing filters or pages keeps them hidden, while a different query resets dismissal. Suggestions remain optional; their failure cannot prevent ordinary results from displaying.

**Why isn't a cache the source of truth?** A cache deliberately forgets records to stay bounded. Forgetting a movie must not mean that movie no longer exists. SQLite supplies authoritative identities; the working cache only speeds up provider operations.

Validation includes eviction beyond 1,500 records, newly saved titles, exact-title suppression, prefix ranking after merging live candidates, missing metadata while browsing, mobile/keyboard dismissal and preservation of filters. Live smoke checks confirmed Interstellar first for `Interstellar`, `Interstell` and `Intersteler`; these checks do not establish general search accuracy.
