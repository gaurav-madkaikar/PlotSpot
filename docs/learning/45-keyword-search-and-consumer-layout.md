# 45: Keyword search and a simpler movie page

## What changed

The production search path no longer embeds a query or asks a model to rank films. It reads the saved SQLite metadata, matches text and returns paginated results. RAG remains useful for facts, quiz and discussion; search has a separate purpose.

The movie page removes the return link and Draft workspace. The global Discover link restores the originating search when available. Movie sections follow the trailer/save actions, and About includes cast/characters. No draft request is made by opening the page or changing spoiler consent.

## Follow one request

1. `frontend/src/components/movie-search.tsx` stores the typed draft separately from the submitted URL query. Enter or the trailing icon submits; filters reset pagination. The icon has an accessible Search name, while native selection/autofill and contained focus use the site's colors.
2. `frontend/src/lib/api.ts` calls `/api/search/catalog`. React Query caches the validated result by query/filter/page parameters under a new keyword-specific key. Old semantic cache entries cannot supply results after the switch. Zod checks the returned Movie records and the keyword match type.
3. `backend/src/movie_companion/main.py` loads `CatalogStore.identity_movies()` in a worker thread. This uses validated SQLite records, including movies fetched through live name lookup. No vector index is needed.
4. `catalog_search.py` normalizes case/punctuation, checks exact and partial title/person identities, then requires every non-filler keyword to exist in actual metadata. Matches can span fields, such as a director name plus a description word. Exact identities rank ahead of descriptions. Results are ordered consistently and paginated only after matching and filtering.
5. `search_suggestions.py` compares known titles/aliases, actors and directors. Suggestions carry real movie IDs. Localized aliases of the same film display one canonical title. Similarity helps spelling correction; it does not establish relevance by meaning.

## Typo correction

An unambiguous known title/person correction takes precedence over individual description words. Otherwise a word must have at least four characters, sufficiently few edits and a unique best candidate. Adjacent transpositions count as one edit. Unknown, short or equally plausible terms stay uncorrected rather than choosing an arbitrary result.

The full corpus exposed an important failure: “Intersteler” tied between two localized aliases of the same movie. Treating different labels as different identities incorrectly fell back to a misspelled description word in another movie. The fix recognizes verified aliases of one movie as one identity, prefers its canonical title and suppresses duplicate suggestions. Ambiguous suggestions for different movies still require a user choice.

## What keyword search does not infer

“hero” matches actual title/person/description/genre words; it does not automatically mean every Marvel/DC film. “communication” need not match “understanding” or “language”. Use exact description words, or choose a title/person suggestion. Explicit genre, language and runtime filters are always applied, even after correcting a typo.

## Historical learning material

The old semantic pipeline is isolated in `legacy_semantic_catalog_search.py`; its exercises and evaluation reports remain historical. Production startup does not construct the semantic search service, and `/api/discover` returns 410. Those past semantic scores do not measure current keyword search.

## Verification

Tests cover identities, descriptions, spelling, ambiguous corrections, aliases, strict filters, stable pagination and new SQLite movies without vectors. Browser checks cover the icon, keyboard Enter, director suggestions, responsive focus/layout, history and absent draft requests. The live nine-query sample in `evals/search/keyword-live-smoke.json` uses 1,533 saved films and records results/timing, including empty results. It is a smoke sample, not a held-out accuracy benchmark.
