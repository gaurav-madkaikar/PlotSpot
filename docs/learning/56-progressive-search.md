# Search that shows saved matches first

## What changed

Previously the grid waited for saved keyword search, two live discovery paths, individual movie hydration, persistence and merged ranking. A locally known film therefore waited on unrelated provider work.

The browser now requests two results concurrently:

```text
Query + filters
  /api/search/local    -> saved title/description rows -> visible grid
  /api/search/catalog  -> verified merged pool         -> completed grid + pagination
```

The completed response wins when present. A local response is only a provisional first page; it cannot publish a pagination token. The completed pool still deduplicates by TMDB ID, freezes ordering and owns later pages. Rows can be added or reordered once on completion of the first page.

`MovieSearch` uses separate TanStack Query keys for each path, containing the same query and filters. Changing queries selects new cache entries and cancels the old browser requests. An older response cannot overwrite a newer query. Local previews are disabled for selected person IDs and completed snapshot navigation.

Saved actor/director name strings cannot distinguish same-name people. The local preview therefore withholds person-only matches; completed discovery still validates person IDs and exact acting/directing credits. Empty local previews leave the loading state visible until live discovery finishes. A failure with usable saved rows keeps those rows and offers retry. A failed local read cannot prevent successful live results from appearing.

## Preparing metadata once

`PreparedCatalog` in `catalog_search.py` contains normalized titles/aliases, actor/director names, description fields, word sets, vocabulary and a suggestion index. Keyword queries reuse these instead of rebuilding them for every keystroke. This is a lexical index, not an embedding/vector RAG database.

`SavedCatalogIndex` owns one current prepared snapshot. A lock prevents concurrent requests from preparing duplicate snapshots. It observes database and WAL file revisions, including writes by another store/process. If a write happens during preparation, the index retries its read; after repeated concurrent writes it returns an uncached snapshot rather than declaring potentially stale data current. SQLite remains authoritative. This is a local filesystem cache, not distributed invalidation.

Startup warms the prepared catalog and suggestion labels before accepting requests. New saved metadata invalidates the snapshot on the next read. This may still require a rebuild after catalog growth. Suggestions reuse their compiled labels until records change, and safe upper bounds avoid expensive similarity comparisons that cannot reach the existing threshold. Genuine prefix completions suppress unrelated fuzzy alternatives.

## What a search tile needs

TMDB search records already supply movie IDs, titles, dates, poster paths, overview, language codes and genre IDs. `movie_preview.py` translates these into the app's movie contract. Cached language/genre configuration supplies readable labels; simultaneous title tiles share that configuration read. Poster URLs must use validated provider image paths.

Complete title-search records need no individual movie-details request. Runtime filters require actual runtime data, which search records omit; those cases fetch the minimal movie endpoint. Person-credit IDs without title records also fetch minimal metadata. These requests do not append credits, videos, keywords or alternative-title collections.

Missing metadata stays unknown. A preview is saved for reuse, but cannot overwrite existing full presentation data or make its old timestamp fresh. Opening a preview-only movie invokes the existing detail loader, which fetches cast, characters, production data and trailer information, then saves the fuller record. Search itself does not fetch scripts or invoke Ollama.

References: [TMDB movie search](https://developer.themoviedb.org/reference/search-movie), [movie details](https://developer.themoviedb.org/reference/movie-details).

## Cache layers

| Layer | Purpose | Lifetime |
|---|---|---|
| SQLite | Saved canonical metadata | Durable; refresh according to completeness/freshness |
| Prepared catalog | Normalize searchable metadata once | One current DB/WAL revision |
| Provider HTTP cache | Reuse API/config responses | Existing bounded ten-minute cache |
| Completed discovery snapshots | Freeze merged results for pagination | Five minutes, up to 64 snapshots |
| Browser completed query cache | Reuse a query/filter/page response | Five-minute freshness |
| Browser saved-preview cache | Show recently fetched provisional rows | One-minute freshness; completed results supersede it |

Cached local rows can temporarily reflect older metadata while live discovery completes. They do not claim global catalog coverage or verified person membership.

## Observed results and limits

`evals/search/progressive-live-v1.json` preserves both initial lazy-index and final startup-warmed runs. Prepared local search measured approximately 6–8 ms over 2,581 saved movies, compared with roughly 220 ms for previous per-query preparation. This is a development observation with different cache/catalog conditions, not a controlled benchmark.

Final startup-warmed HTTP previews measured approximately 29 ms for Interstell, 10 ms for Casablanca and 17 ms for The Secret of Roan Inish. Their completed discovery requests took approximately 797, 372 and 232 ms. The 350 ms typing debounce and browser rendering are excluded. The previously absent Roan Inish movie was discovered/persisted in the initial run; a subsequent detail read confirmed that cast/presentation loaded only on opening.

Tests cover cache reuse/invalidation, concurrent writes, unchanged lexical results, prefix suggestions, lightweight title tiles, missing runtimes, identity validation, stale-detail preservation, source failure, delayed live responses, query switching, strict filters and stable pagination. These checks do not establish production throughput or general retrieval/LLM accuracy.
