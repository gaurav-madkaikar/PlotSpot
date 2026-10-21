# Pairing checkpoint — your mapper in a live application

You wrote `map_tmdb_details`. We reviewed Pydantic construction-time validation, dictionary access, and extracting names with a list comprehension. The assistant extended the mapper and then built the surrounding integration.

## Follow one request

1. `frontend/src/pages/discover.tsx` collects URL filters, derives the cache key, and calls `searchMovies`.
2. `frontend/src/lib/api.ts` requests `/api/search`; the Vite development proxy forwards it to FastAPI.
3. `backend/src/movie_companion/main.py` validates inputs and selects the provider. Demo mode uses the fixture catalog. Live mode uses `TmdbClient` created in the application lifespan.
4. `tmdb_client.py` queries titles and people. A single exact actor-name match can contribute that person's cast credits. Ambiguous names are not guessed. With an empty query, the provider lists the first discovery page.
5. The provider deduplicates candidate IDs and fetches details/credits for at most 20 movies. Network work uses a shared four-slot semaphore. A cached language lookup translates original-language codes into display names.
6. Your mapper converts each details dictionary into `TmdbMovieDetails`. The client adds overview, director, cast, and an allowed TMDB poster URL, then creates the app's `Movie` contract.
7. The provider applies genre/runtime/language constraints and returns the bounded results. `total` counts the returned records; `limited=true` identifies the bounded search.
8. Zod checks the arriving JSON before React renders cards. Unknown dates/runtimes remain `null`, and missing/failed posters use an accessible placeholder.

## Why the separate modules?

The mapper transforms data without network access. The client handles HTTP, caching, and provider-specific composition. Routes handle our public API and request validation. React handles interaction and rendering. Each boundary can be tested independently; the app doesn't need to know the raw TMDB response shape.

The lifespan owns one HTTP client and closes it when the server stops. Reusing the client reuses connections. `Depends(get_provider)` makes routing testable: a test can substitute a fake provider without making internet requests.

## Failure and resource behavior

- Missing or rejected credentials: safe 503 configuration error.
- TMDB 429: safe 503 indicating a request limit, without blind retries.
- Upstream outage or malformed JSON/data: safe 502.
- Network or overall search timeout: safe 504.
- Missing movie: 404; a candidate that disappears during hydration is omitted.
- Other detail failures fail the search, rather than quietly returning an incomplete-looking success.
- Raw upstream errors and authorization values are never returned by the API.
- Requests use a fixed HTTPS origin, do not follow redirects, and expose no arbitrary browsing/shell action.

The cache stores successful JSON for ten minutes and retains at most 256 entries. It is in memory and vanishes on restart. Upstream response shape is validated by the provider and mapper. A runtime limit excludes movies whose runtime is unknown because the system cannot prove they satisfy that constraint.

## What changed in the UI?

The Python and TypeScript contracts now agree on nullable fields and demo/TMDB source labels. Official posters have their own alt text; illustrations remain identified as illustrations. The About page includes TMDB attribution. The featured hero still uses an original Interstellar illustration; result tiles and detail pages use available TMDB posters in live mode.

The collection now queries each saved ID directly. Filtering the discovery page no longer makes an already saved movie disappear. Saved IDs refer to TMDB movie IDs shared by our fixtures. Unavailable saved movies can be removed deliberately. Browser-local saves and spoiler preferences are still temporary account-free storage.

## Measured verification

Backend tests use mock HTTP transport and safe dummy tokens. An autouse fixture forces offline settings even if your local `.env` contains a real token. Browser tests also start demo-mode backends and use mocked live responses. The user authorized a separate real TMDB smoke check: Interstellar details/cast/poster and Arrival with English/science-fiction/runtime filters succeeded. No real token was printed or copied into the repository.

This is API integration, not an agent evaluation. Agent quality and prompt-injection evaluations will accompany the later Ollama/RAG milestones.

## Explain it back

- What would happen if runtime stayed required in Python but became nullable only in TypeScript?
- Why does the collection fetch saved IDs rather than filter the current discovery response?
- Which work runs concurrently, and what bounds it?
- What does the ten-minute cache save, and what does it not guarantee?
- Why can a bounded filtered search return zero results even when a matching movie exists elsewhere in TMDB?

## Answers to revisit

### 1. What if runtime stayed required in Python but became nullable only in TypeScript?

If the Python contract still accepted only a positive integer, constructing a movie with `runtime_minutes=None` would fail backend validation before the frontend could receive it. Making the frontend nullable cannot repair a backend rejection. The reverse mismatch is also a problem: if Python emits `null` while Zod accepts only numbers, the browser rejects the response.

Both boundaries now accept an unknown runtime and the UI displays “Runtime unavailable.” Nullable and optional are separate concepts: `int | None` permits a null value, while `= None` also provides a default when the field is omitted. Our Zod `.nullable()` permits `null`, not an omitted field; FastAPI emits the nullable field in its normal response. Do not invent a duration such as 1 minute merely to satisfy validation.

### 2. Why fetch saved IDs rather than filter discovery results?

Discovery is a changing, bounded subset of the catalog. A saved movie can be absent because the query changed, filters exclude it, its popularity changed, or it is beyond the first candidate page. Filtering that subset by saved IDs would make a valid save appear lost.

The collection uses `getMovie(id)` for each saved ID, independently of discovery. Its query keys can reuse detail data already loaded elsewhere. An unavailable movie is shown as a retrieval problem and can be removed deliberately; we do not silently delete the user's save when an API call fails.

### 3. Which work runs concurrently, and what bounds it?

Title search and person search run concurrently through `asyncio.gather`. A movie's details-with-credits request and language lookup can also run concurrently. After candidate IDs are selected, up to 20 movie hydration tasks are scheduled together. The shared language lookup is populated before that batch so most hydration calls reuse it.

Scheduling 20 tasks does not mean sending 20 requests simultaneously. A semaphore permits four active upstream requests, and the reusable HTTP client allows at most four connections. Requests have an 8-second HTTPX timeout, while the overall search has a 30-second deadline. These are asynchronous network tasks, not multiple LLM agents. Actor-credit retrieval depends on person resolution, so that dependent step follows the person response.

### 4. What does the ten-minute cache save, and what does it not guarantee?

It saves repeated upstream network work, latency, and provider quota usage by storing parsed JSON responses. The key combines endpoint and supplied parameters. Values contain a monotonic expiry time and payload. Hits update recency but do not extend the ten-minute expiry. `OrderedDict` allows least-recently-used eviction once capacity exceeds 256 entries.

It does not guarantee that data is current within that period, that all simultaneous misses are deduplicated, or that results persist across restarts. Each backend process has its own cache. Capacity counts entries rather than bytes, and expired entries are removed lazily on access or through capacity eviction. Errors and invalid JSON are not cached, but a successful JSON object/list is cached before full movie-schema validation, so basic cache acceptance does not itself establish complete metadata validity.

This cache does not store poster image bytes or final filtered application results. Those have different consumers and inputs. React Query caches final API results in the browser separately, and the browser may cache images according to their HTTP headers.

### 5. Why can bounded filtered search return zero despite a match elsewhere?

The current implementation selects at most 20 candidate IDs from a first search/discovery page or actor-credit candidates. It hydrates those records and applies genre/runtime/original-language constraints locally. A qualifying movie outside that candidate set is never considered. The correct interpretation is “no qualifying results among these candidates,” not “no qualifying movies exist in TMDB.”

The response marks `limited=true`, `total` counts returned records, and the UI discloses the limit. A later improvement could push compatible constraints into TMDB discovery, add pagination or expand candidates under a budget. Each approach trades network work and latency against coverage; a similarity or semantic ranking algorithm cannot recover a movie that was never included in its candidate set.

Next pairing slice: a typo-tolerant search baseline with a small labeled set, before adding semantic retrieval.
