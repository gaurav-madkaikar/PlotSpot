# 23 — One search bar, a larger catalog, and real pagination

## What changed

The old search forced you to choose between Title/cast and Mood/story. One bar now accepts either. Its label is **Find your next film** and its placeholder is **Title, actor, genre, or mood…**. Search submits deliberately; typing does not embed every keystroke. Changing a filter updates the submitted request. Old `mode=meaning` links preserve the query and remove the mode parameter.

The saved catalog now has 200 real TMDB films, including 20 tagged Romance. Browse shows 20 records per page. Discussion evidence still covers ten films; saved Quiz/Facts are still Interstellar-only. Increasing discovery coverage does not automatically create evidence or AI content for every movie.

## How the data is prepared

`catalog_import.collect_movies()` fetches TMDB's genre list and bounded discovery pages. It takes candidates round-robin across genres instead of filling the collection with one genre. Known ten seed IDs remain first. Each canonical ID is resolved through the existing TMDB adapter; invalid identities fail, adult discovery records are excluded, missing synopses and vanished records are skipped in favor of remaining candidates. Metadata fetches have bounded batches and a four-request provider semaphore.

We persist title, ID, year, synopsis, genres, language, runtime, director, poster URL and six main cast names. We save URLs rather than downloading images. The importer receives fuller credit data, but stores only the main cast for search; the existing detail API supplies additional cast/details when you open a film. Main-cast search is not every credited actor's complete filmography.

`prepare_semantic_catalog.py` reuses embeddings whose searchable text is unchanged, embeds changed descriptions through your `embed_texts()` helper in batches of 16, and atomically saves `data/private/semantic-catalog.json`. No `--refresh` means no source or model requests if a catalog already exists. Failure before publication preserves the old snapshot. Only IDs validated by the importer enter its identity manifest; viewer queries cannot add IDs or edit this file.

The 200-film metadata/vector snapshot is around 2 MB. A validated JSON snapshot with exact vector comparisons is sufficient at this scale. SQLite or a dedicated vector collection becomes useful when larger imports, incremental updates and concurrent writers justify it. It is separate from Chroma's article passages and SQLite's saved quizzes/facts.

## Following one request

Frontend `components/movie-search.tsx` gathers the submitted query and filters. `lib/api.ts` calls `GET /api/search/catalog?q=romance&page=1&page_size=20`. `main.py` validates bounds and passes a `CatalogQuery` to `catalog_search.search_catalog()`.

1. Load validated catalog metadata; apply explicit genre/language/runtime filters.
2. Recognize direct genre requests. **Romance** requires the Romance metadata tag, and **romantic comedy** requires both Romance and Comedy. Common explicit negation such as “comedy without romance” excludes Romance. The parser is a conservative English rule set, not a full natural-language interpreter.
3. Prioritize normalized title and main-cast matches. A movie title containing a genre word still matches as an identity. Explicit UI filters continue to apply; typing Interstellar cannot override a 120-minute maximum.
4. Try conservative fuzzy matches against known title/cast labels. A correction maps to saved canonical IDs, never invented IDs. The response includes the correction, and optional suggestions remain available.
5. For a descriptive query, require some support in the stored synopsis, with a small English synonym map. This prevents the old behavior of always filling six nearest slots. Unsupported terms can yield zero results without an AI call. It can also reject valid paraphrases; one shared term does not prove full relevance.
6. Embed supported descriptions' query through your learner helper, reuse the existing bounded query cache, then rank with your cosine function. This is retrieval, not a chat model inventing recommendations. No shell/write/web-action tools are available to the query.
7. Slice the filtered, ranked list for the requested page and return actual records. Genre results report applied genres, and cards display the matching genre even if TMDB lists a different one first.

Pure titles, cast names, genres and blank browsing do not require Ollama or TMDB at search time. Descriptive queries with candidate support need local Ollama. The saved catalog endpoint does not require a TMDB token just to read existing records; opening live details still uses the configured provider.

## What pagination actually means

The backend does this **after** filtering and ranking:

```python
start = (page - 1) * page_size
items = ranked[start:start + page_size]
total = len(ranked)
total_pages = math.ceil(total / page_size)
```

For the unfiltered catalog, page 2 returns records 21–40, while `total` stays 200 and `total_pages` stays 10. For romance, there are 20 matches and one page. The browser receives only the current page; it does not fetch 200 cards and hide 180.

Previous/Next update the URL and preserve query and filters. A new search/filter resets page to 1. Browser Back restores the previous page. Page bounds are checked by the API. A valid page number beyond available results returns an empty page with the true total, and the UI offers First page rather than claiming there are no matches.

## Where caching fits

- Persistent catalog: survives restarts, read by page/search requests, replaced only by explicit preparation. It contains movie metadata and document embeddings.
- Backend query-vector cache: five minutes, 64 entries. Same-query requests share an in-flight embedding, while their filters/pages remain independent. Page changes can reuse the same query vector.
- Frontend React Query cache: keyed by complete serialized request, including query, filters and page. Page 1 and page 2 never overwrite each other. Results remain fresh for five minutes.
- Existing provider cache: caches TMDB responses in memory during preparation/detail fetches. This is separate from the persisted discovery catalog.

## What the evals tell us

Real 200-film checks passed all ten identity, genre, unsupported-request, constraint and page-isolation cases. Browse returned ten non-overlapping 20-film pages. Romance results all carry the Romance tag; the old Dune-style arbitrary nearest matches are gone.

The ten descriptive development queries placed the expected film first in 5/10 and within the top five in 8/10. The misses are retained in `evals/discovery/unified-200-ollama.json`. This is a larger, harder candidate set than the earlier ten-film smoke check, and the query set is not held out. These measurements do not prove broad recommendation quality.

A sensible next experiment is comparing a lexical/BM25 baseline, hybrid retrieval and a reranker on a held-out set. Test valid paraphrases as well as unrelated requests: preventing false positives should not silently erase good matches. Do not pick an arbitrary cosine threshold and call it safety or confidence.

## Answers to common questions

**Why store genres and runtime if details load later?** We need them before ranking to enforce constraints. Unknown runtime is excluded when a runtime limit is requested.

**Why not give every movie a script and quiz now?** Discovery only needs compact searchable metadata. Evidence retrieval and content preparation are separate, more expensive tasks with their own coverage and verification requirements.

**Does an actor search cover all their movies?** It covers main-cast appearances in the saved 200-film collection. Complete filmography and name disambiguation are future work.

**How does the backend know whether I meant a title or a mood?** This version uses ordered deterministic checks before semantic retrieval. That makes routing predictable and testable without requiring a chat agent for each search.

**Are the negative evals just fixed-output tests?** Genre/identity/page cases can check exact IDs or metadata properties. Semantic cases label which movie should appear among the first few, rather than expecting a fixed vector or identical generated text. Empty-result cases test a different property: unrelated candidates must not be presented as matches.

## Commands from the project root

```sh
backend/.venv/bin/python backend/scripts/prepare_semantic_catalog.py --refresh
backend/.venv/bin/python backend/scripts/evaluate_unified_search.py
backend/.venv/bin/pytest -q backend/tests
npm --prefix frontend run build
```

You can inspect `search_intent.py`, `catalog_search.py`, and `movie-search.tsx` in that order to see query interpretation, backend ranking/pagination, then UI state. Your embedding/cosine helpers remain the foundation of the semantic branch.
