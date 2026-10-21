# TMDB Integration Plan

> Execution: inline pair programming. The learner completed the mapper; the assistant extends the approved integration. No delegation.

**Goal:** Enable explicit live TMDB mode with title/exact actor search, filters, details, posters, and a working saved collection.

**Architecture:** A server-side provider owns bounded HTTP requests, TTL caching, and provider errors. FastAPI keeps the existing movie contract with explicit nullable metadata and source flags. React validates that contract, labels sources, and renders poster fallbacks. Demo mode stays deterministic and independent of credentials.

**Tech Stack:** existing FastAPI/Pydantic/React stack plus runtime HTTPX and python-dotenv.

## Boundaries

- Credentials live only in backend environment or ignored `backend/.env`.
- Explicit `MOVIE_DATA_SOURCE=demo|tmdb`; missing credentials in live mode produce a safe 503.
- Fixed HTTPS TMDB origin; redirects disabled; 8-second request timeout; 30-second search budget; 4 simultaneous upstream requests.
- TTL cache: 10 minutes, at most 256 entries; no persistent private credential data.
- One candidate page, at most 20 detailed movies per search; returned counts describe that bounded set, not all TMDB matches.
- Exact actor-name resolution first; typo/semantic improvements are subsequent pairing slices.
- No ratings or agent content in this batch.

## Tasks

- [x] Add settings, runtime dependencies, and `.env.example`; validate source choice without printing credentials.
- [x] Create `tmdb_client.py`: fetch fixed endpoints, compose details/credits/language names, cache successful JSON only, map timeout/auth/rate-limit/malformed responses to safe errors.
- [x] Implement title/actor candidate search and apply genre/runtime/original-language filters to hydrated records; preserve unknown optional values.
- [x] Wire provider dependencies and lifespan resource cleanup into `main.py`; update Python and TypeScript contracts together.
- [x] Update discovery/details/collection for source labels, posters, unknown metadata, and direct saved-ID loading. Include TMDB's approved logo and attribution.
- [x] Test HTTP behavior via mock transport: caching, authentication, timeouts, upstream failures, invalid payload, bounded search/filtering, actor credits, and missing data. Verify provider wiring without secrets.
- [x] Run backend tests/build/browser checks using demo fixtures and mocked live contracts. Perform actual upstream smoke check only once a local credential is configured.
- [x] Record outcomes and a walkthrough of the mapper/client/provider/UI flow.

References: https://developer.themoviedb.org/reference/movie-details ; https://developer.themoviedb.org/reference/search-movie ; https://developer.themoviedb.org/reference/search-person ; https://developer.themoviedb.org/reference/person-movie-credits ; https://developer.themoviedb.org/docs/faq

Verification: 45 backend cases, 13 browser journeys, production build, and actual live detail/search/UI checks passed. Results are documented in docs/learning/PROGRESS.md. Fuzzy search and actor-disambiguation UI remain subsequent slices.
