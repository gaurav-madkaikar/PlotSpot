# Checkpoint 1 — learn the product boundary

This is a small runnable foundation, not the completed agent project. First understand a deterministic request; it makes later retrieval and agent failures much easier to diagnose.

## Run and explore

Follow the root README. Search for **Amy Adams**, choose **Science Fiction**, and set runtime to **Under 2 hours**. Open Arrival. Go back. Save it, open My collection, and reload. Open a movie’s Quiz tab and notice that the app tells you it is unavailable rather than inventing sample results.

For the exercises in this checkpoint, set `MOVIE_DATA_SOURCE=demo` and restart the backend. No model or API key is needed in demo mode. The app now also supports live TMDB mode, but its changing results should not be used to justify the fixture-based expectations below. This deliberate baseline is reproducible and can later be compared with more complex approaches.

## Follow one request

```text
Search field changes
  → DiscoverPage immediately updates the URL to preserve your intent
  → the API query waits 250ms to avoid a request for every keystroke
  → TanStack Query uses the URL fields as a cache key
  → api.ts sends GET /api/search?q=Amy+Adams&genre=Science+Fiction&max_runtime=120
  → Vite proxies /api to FastAPI
  → main.py validates query parameters
  → catalog.py filters validated demo records
  → schemas.py defines the JSON response contract
  → contracts.ts checks that JSON at runtime
  → MovieCard renders each result using its stable movie ID
```

Open `backend/src/movie_companion/main.py`, then `catalog.py`, then `frontend/src/lib/api.ts`. These are intentionally small. Read `frontend/src/pages/discover.tsx` after those boundaries make sense.

**Why two schemas?** Python validates what the backend produces; TypeScript types help while coding the UI. External JSON still arrives at runtime, so Zod validates it rather than trusting a type assertion. Later we can generate types from OpenAPI, but runtime data checks still serve a different purpose.

**Why put search in the URL?** A URL can be bookmarked, shared, or restored by back navigation. Component-only state disappears when the component unmounts. Local collection state has a different job: it persists a temporary browser preference.

An early browser test caught a race: delaying the URL update as well as the request lost a typed query when a film was opened quickly. We fixed it by persisting the query immediately and debouncing only retrieval. The test stays as a regression check.

**Why pass an AbortSignal?** If a user changes a query quickly, older work can become irrelevant. Cancellation prevents a superseded response from taking over the current experience and avoids unnecessary work. An agent run will need the same idea at a larger scale.

The signal lets the browser cancel its fetch. This does not guarantee that FastAPI or TMDB stops work already started on the server; server-side cancellation needs its own propagation. Distinct query keys also keep results for different searches separate.

**Why no agents yet?** Basic catalog matching is a deterministic data task. Introducing an LLM now would add latency and invented-result risk without solving the current problem. Agents arrive when there is evidence gathering, planning, and bounded recovery to justify them.

## Your first small exercise

Before adding live data, write a backend test for this request:

```text
/api/search?genre=Drama&max_runtime=120
```

Predict the exact movie titles, run the test, and inspect any mismatch. Use the fixture records to justify your expectation. This is practice in specifying behavior before changing implementation.

Then change the maximum runtime to 100 in your test and explain the difference. We will review this together rather than automatically completing the exercise for you.

## Explain these decisions in your own words

1. What would break if the UI used array positions instead of movie IDs?
2. Why is a 404 different from an empty search result?
3. What does TypeScript fail to guarantee about an API response?
4. Why does a browser checkbox not establish a future backend authorization boundary?
5. Which part would change when TMDB replaces authored fixtures, and which parts should remain stable?

## Answers to revisit

### 1. What would break if the UI used array positions instead of movie IDs?

An array position identifies where a movie happens to be in one result list, not which movie it is. If Arrival is at position 0 and filtering puts Parasite at position 0, storing a save by position would now refer to Parasite. A movie ID remains associated with Arrival across sorting, filtering, and navigation.

React's `key` has a related role: it associates a component instance with an item. Using an index as the key when a list reorders can attach component state or focus to the wrong item. We use `key={movie.id}` for rendering and the actual ID for saves and `/movies/:movieId` routes. These are related uses of identity, but a React key does not itself create a route or save record.

### 2. Why is a 404 different from an empty search result?

Searching asks for a collection of matching records. If no records match, the search succeeded and returns HTTP 200 with `items: []` and `total: 0`. Looking up a particular movie asks for one identified resource; HTTP 404 means that resource is unavailable from the selected provider. Invalid input, such as a nonnumeric movie ID, is a separate case and receives HTTP 422.

The UI can therefore show “No films found” for a successful empty search, a missing-movie page for 404, and a retry panel for a temporary provider failure. Treating all three as empty results would hide operational problems.

### 3. What does TypeScript fail to guarantee about an API response?

TypeScript checks our code during development/build; it does not inspect incoming JSON at runtime. Writing a type assertion such as `data as Movie` cannot make a missing `title`, an invalid poster URL, or a string runtime become valid movie data. HTTP responses originate outside the frontend's type system.

Zod parses the actual response and checks the runtime shape before rendering. Pydantic validates backend models, while Zod validates what the browser actually receives. These checks complement each other; neither proves that an overview is factually correct or that a movie is relevant to the user's query.

### 4. Why does a browser checkbox not establish a future backend authorization boundary?

The user can alter browser state or call the API directly without using the checkbox. The current spoiler checkbox is a browser-local preference, not a security control enforced by the server.

When grounded story features arrive, the backend must establish the requested spoiler mode and enforce it before retrieving evidence or calling the model. Private records also require server-side ownership checks. A frontend control communicates intent; it cannot authorize access on its own. Spoiler preference and permission to read another user's private data are distinct decisions.

### 5. Which part changes when TMDB replaces authored fixtures, and which parts remain stable?

The data-access implementation changes: reading `movies.json` becomes calling the TMDB provider, mapping its fields, composing credits, and handling caching, timeouts, authentication, and unavailable metadata. `main.py` now selects demo or live behavior through `get_provider`.

The public route concepts, validated movie/search contract, movie IDs, URL-backed filters, and card/detail interactions remain the boundary the UI depends on. The contract can evolve deliberately: live integration added nullable metadata and source/artwork flags to both Python and Zod together. Stability means hiding provider-specific response shapes behind our API, not promising that the contract will never change.

### Exercise answer: Drama within 120 minutes versus 100 minutes

In the ten authored fixtures, Drama with `max_runtime=120` returns **Arrival (116 minutes)** and **The Truman Show (103 minutes)**. At `max_runtime=100`, neither qualifies, and no other Drama fixture fits, so the result is empty. The Grand Budapest Hotel is 100 minutes long but its fixture genres are Comedy and Adventure; runtime alone is insufficient.

An assertion comparing the complete sorted title list verifies both membership and count. Merely asserting that Arrival and The Truman Show are present could overlook an extra or duplicate result. The same hard-coded expectations do not apply to the changing live catalog.

## What we verified

API tests cover actor matching, combined constraints, invalid input, unique records, data-source honesty, and missing IDs. Browser tests cover the connected user journey, persistence, keyboard tabs, empty/error recovery, corrupt storage, mobile overflow, and reduced motion. These are product checks; they are not agent evaluations.

## Next checkpoint

Connect TMDB behind this contract, introduce a provider adapter and cache, then evaluate spelling recovery and actor disambiguation against a small labeled search dataset. Add API credentials only to backend configuration. Live source availability and attribution become part of the behavior we test.
