# 30. External name search and director credits

The assistant completed this integration at your request. You can read the full flow before choosing another main AI exercise.

## Follow a request through the app

1. `MovieSearch` searches saved identities first and keeps story/mood recommendations local. Director names now count as identities too.
2. Click **Search titles and people** to open `NameSearchPanel`. There is still one search bar. This explicit action avoids treating an unfamiliar story description as a movie title.
3. `searchNames` in `frontend/src/lib/api.ts` sends a GET request. Zod checks the response in `contracts.ts`.
4. `/api/search/names` validates the query, page, filters, person ID and role, then calls `search_names` in `backend/src/movie_companion/name_search.py`.
5. Title and person searches run together with `asyncio.gather`. Selecting a person instead retrieves that person's profile and movie credits together.
6. At most 20 movie IDs are hydrated into complete Movie records per request. Saved fresh records skip hydration. Valid newly fetched records are saved transactionally in SQLite.
7. The response returns movie tiles, distinct person choices, the current page, continuation and partial-failure flags. It doesn't claim a global filtered result count.

Try these application requests:

```text
/api/search/names?q=Christopher%20Nolan
/api/search/names?q=Christopher%20Nolan&person_id=525&role=director
/api/search/names?q=Christopher%20Nolan&person_id=525&role=actor&page=2
```

The API response is shaped like this (illustrative, not a complete Movie record):

```json
{
  "items": [],
  "people": [{"id": 525, "name": "Christopher Nolan", "adult": false,
    "known_for_department": "Directing", "known_for_titles": ["Interstellar"]}],
  "selected_person": null,
  "role": "actor", "page": 1,
  "has_more": false, "partial": false, "limited": false
}
```

## Why names and departments are not enough

Our setup live search returned several people named Christopher Nolan. A canonical person ID distinguishes them; the UI shows their department and known films where available.

`known_for_department == "Directing"` describes a person's profile. It does not mean every film credit is a directing credit. Movie credits have separate `cast` and `crew` arrays. Cast establishes acting appearances; crew contains jobs such as Director, Producer, Writer and Director of Photography.

The selector is:

```python
return list(dict.fromkeys(
    record["id"] for record in crew if record["job"] == "Director"
))
```

The expression filters records by exact job, keeps each ID once, and preserves order. `dict.fromkeys` constructs keys in insertion order; converting those keys to a list gives the final IDs. The provider validates each record's ID/job before the selector runs.

`Director of Photography` is a different role and is excluded from directed films. Adult films are **included**, as requested. `adult` is stored as `true`, `false`, or `null` when unknown; there is no preference filter yet. The title/person requests and future catalog discovery use `include_adult=true`. The existing semantic snapshot hasn't been regenerated.

Run the small deterministic example:

```sh
backend/.venv/bin/python backend/scripts/try_director_credits.py
```

Expected IDs: `[101, 303, 505]`. It checks role selection, duplicate removal, cinematographer exclusion, adult inclusion and empty input.

## Async, caching and persistence

`await` yields control while a request waits. `asyncio.gather` deliberately schedules independent calls together. TMDB's existing semaphore permits at most four provider requests concurrently; a whole name lookup has a 30-second deadline. Each HTTP read uses the existing eight-second timeout.

There are three different storage layers here:

- TanStack Query caches parsed name-search responses in the browser for five minutes, keyed by query, filters, page, person ID and role.
- `TmdbClient` caches upstream HTTP payloads in memory for ten minutes, with at most 256 entries. This disappears when the backend restarts.
- `CatalogStore` saves validated movie metadata to SQLite, surviving backend restarts. Metadata is fresh for seven days. A stale record remains usable when refreshing it fails, without giving it a new freshness timestamp.

If one provider search or one movie hydration fails, good results remain and the UI offers retry. If external search fails completely, existing local movie results remain below it. Filters apply to each bounded provider page, so a page can be empty while later pages still contain matches.

New saved movies become searchable by their title, cast and director, and their detail pages open without waiting for AI generation. They do **not** enter story/mood search until a separate preparation publishes embeddings. Facts, quizzes and evidence preparation are also separate.

## Questions and answers

**Why not select the first person with a matching name?** Different people can have the same name. The user chooses the correct profile, and subsequent requests use its ID.

**Why not combine cast and crew?** That would present films someone produced or wrote as films they acted in or directed.

**Why hydrate candidates?** Search responses contain incomplete metadata. The details endpoint supplies the validated fields required by movie cards and the expanded view.

**Why not fetch every film in a person's career at once?** Bounded pages avoid hundreds of detail calls, latency and unnecessary upstream load.

**Why save metadata without creating vectors?** Displaying a movie needs metadata; semantic retrieval needs prepared embeddings. Keeping them independent makes detail pages fast and lets embedding publication remain deliberate.

**Does this flow need an LLM?** No. Name matching, credit roles, IDs, paging and persistence use deterministic code and TMDB. Ollama remains involved in local semantic retrieval and the separate RAG/AI features.

Official references: [movie-name search](https://developer.themoviedb.org/reference/search-movie), [person-name search](https://developer.themoviedb.org/reference/search-person), [person movie credits](https://developer.themoviedb.org/reference/person-movie-credits).
