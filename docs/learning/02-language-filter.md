# Hands-on feature — movie language filtering

Completed on 2026-10-08: the learner implemented the backend and frontend slices; the assistant completed browser regression coverage. Verification: 9 backend tests, 9 browser journeys, and the production build passed. Future exercises use the updated pairing workflow in `PROGRESS.md`: the learner codes one representative slice, then the assistant extends the feature to completion.

The original exercise below records the behavior and concepts practiced. This is actual app functionality, using the current demo data before introducing an external API.

## User-facing goal

Add an **All languages / English / Korean / Japanese** filter to movie discovery. It must work together with search, genre, and maximum runtime, remain in the URL when you open a film and return, and use the same loading/empty/error behavior as other filters.

Here `language` means the language field on our demo records. TMDB integration will later make the distinction between original language and other spoken languages explicit.

## Slice A — backend first

Read these three files:

1. `backend/tests/test_api.py`: your current HTTP-level tests.
2. `backend/src/movie_companion/main.py`: validates request parameters and forwards them to catalog logic.
3. `backend/src/movie_companion/catalog.py`: applies filtering to validated records.

Add an optional `language` query parameter to `/api/search`. Keep existing callers working when it is omitted. Extend `search_movies` with an optional `language` argument at the end of its signature, and forward the new value from the route by keyword. Apply the language condition alongside the current conditions, not in place of them.

Behavior:

| Request | Expected titles |
|---|---|
| `language=Korean` | Parasite |
| `language=japanese` | Spirited Away |
| `language=English&max_runtime=120` | Arrival, The Truman Show, The Grand Budapest Hotel |
| `language=Korean&max_runtime=120` | No results |
| Language omitted or empty | Existing behavior |
| `language=Martian` | No results, HTTP 200 |

Ignore leading/trailing whitespace and case in nonempty language values. Limit the query parameter to 40 characters; oversized inputs should return HTTP 422, consistent with the existing genre parameter.

Start by writing one test for the Korean request. Run it before changing the feature and explain the failure. Implement only enough to make that case work, then add combined-filter and omitted-language coverage. Your existing tests must keep passing.

Hints, in order:

- Follow how `genre` travels from the route into `search_movies`.
- `movie.language` already exists; this feature does not require changing the movie schema.
- An absent language should allow every movie through that particular condition.
- Normalize comparison values using the same case-insensitive concept as the current search code.
- Additional constraints combine with `and`: a film must satisfy all active filters.

Run from `backend`:

```sh
uv run pytest tests/test_api.py -q
```

**Review checkpoint:** show your backend attempt before moving to the frontend. Explain why FastAPI should validate input length while the catalog handles matching.

## Slice B — connect the frontend after review

Work in `frontend/src/pages/discover.tsx`:

- Read the language value from `useSearchParams`, as the existing genre/runtime values do.
- Add it to the parameters passed to the search client. The resulting search key must include language, so cached results for different languages remain distinct.
- Add an accessible native select with a label and the four choices above. Reuse `updateFilter` to update the URL.
- Include language in the condition that displays **Clear filters**. Clearing filters must remove language too.
- Verify that the toolbar remains usable on a 375px-wide screen. Existing layout styles may already support the extra control; inspect before changing CSS.

There is no need to change `api.ts` for a new query field: it already accepts URLSearchParams. There is no need to hardcode filtered result arrays in React; the backend owns matching.

Manual checks: selecting Korean shows Parasite; combining it with the two-hour limit shows the empty state; clearing filters restores all films; opening Parasite and returning preserves the language selection. Then add one browser journey for that flow in `frontend/e2e/foundation.spec.ts`.

Run the frontend build and browser checks after your code is ready. Browser tests start their own servers, so stop manually running app servers first.

## Concepts to explain afterward

1. Request validation versus business logic.
2. Optional Python parameters and backward compatibility.
3. Combining independent constraints.
4. Controlled React inputs and URL-backed state.
5. Why a query cache key must contain every field affecting the result.
6. Why passing backend tests does not guarantee correct frontend wiring.

## Answers to revisit

### 1. Request validation versus business logic

Request validation checks whether input is acceptable at the API boundary. FastAPI checks that `max_runtime` is an integer within its allowed range and that `language` is no longer than 40 characters; invalid requests receive HTTP 422 before matching begins.

Business logic decides which movies satisfy a valid request. The catalog/provider normalizes `" korean "`, compares languages, and combines genre/runtime constraints. `"Martian"` is valid input structurally but matches no language in the catalog, so it returns a successful empty result rather than a validation error.

This also answers the backend review checkpoint: FastAPI owns HTTP input constraints; matching belongs in reusable catalog/provider logic that can be called without HTTP. Plain Python type annotations alone do not enforce runtime validation.

### 2. Optional Python parameters and backward compatibility

In `language: str | None = None`, the annotation allows either a string or `None`; the default makes supplying the argument optional. Without `= None`, an argument can allow `None` as a value while still being required when calling the function.

Existing calls such as `search_movies("Arrival")` continue working because the new parameter defaults to no restriction. Placing it at the end preserves the meaning of existing positional arguments. Forwarding it by keyword makes the call easier to understand as parameters accumulate. Normalize before checking emptiness so omitted, empty, and whitespace-only language values all mean no filter.

### 3. Combining independent constraints

Active filters combine with `and`: a movie must satisfy the query, genre, runtime, and language restrictions together. An inactive filter contributes `True` and leaves the remaining restrictions in control.

Parasite satisfies Korean but its 132-minute runtime fails a 120-minute maximum, so the combined demo result is empty. Using `or` between those active filters would admit films satisfying only one requirement. In live mode, a movie with unknown runtime is excluded when a runtime maximum is active because we cannot establish that it qualifies.

### 4. Controlled React inputs and URL-backed state

The dropdown is controlled because React supplies its `value`. We derive that value from `params.get('language') ?? ''`, making the URL the source of truth instead of maintaining a second independent language state.

Selecting Korean calls `updateFilter`, which updates the URL. React renders with the new URL value, request parameters change, and React Query loads that result. Refreshing, sharing a URL, and navigating backward can restore the filter. Choosing the empty option removes the parameter. Its displayed label is “All languages,” but `value=""` is the submitted value; label text and request value serve different purposes.

### 5. Why the query cache key contains every field affecting the result

React Query identifies the final search response using `['movies', searchKey]`. `searchKey` includes query, genre, maximum runtime, and language. Omitting language could make Korean and Japanese searches share an entry, causing the UI to reuse results for the wrong selection.

This is the frontend cache. The backend TMDB cache stores individual upstream responses, keyed by their endpoint and parameters. Runtime filtering is performed locally, so changing runtime can correctly reuse the same cached TMDB movie details while producing a different final search result. A cache key must reflect the inputs affecting the particular value that cache stores.

### 6. Why backend tests do not guarantee correct frontend wiring

Backend tests call `/api/search?language=Korean` directly. They verify what the API does with that request, but cannot establish that the UI constructs it, updates its cache key, renders its results, or clears the parameter correctly.

Our missing option-value bug demonstrated this: the UI submitted `"All languages"` instead of an empty string. The backend correctly returned no matches for that value even though its language tests passed. Browser tests verify the connected journey: dropdown selection, results, detail/back navigation, reload persistence, combined-filter empty states, and clearing.
