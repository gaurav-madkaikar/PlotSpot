# TMDB Mapping Pairing Plan

> Execution: inline pair programming, as explicitly selected by the user. The learner writes one representative mapper; the assistant reviews and completes the integration afterward. No delegation or full mapper solution before the learner's attempt.

**Goal:** Establish a tested boundary between external TMDB records and the application's movie data.

**Architecture:** Translate movie-details dictionaries into a Pydantic provider model before adapting them to the application contract. Keep absent date/runtime/poster values unknown; retain original-language codes until display-language lookup. The learner's mapper is not yet wired into application routes.

**Tech Stack:** Python 3.12, Pydantic, pytest; existing FastAPI backend.

## Scope and files

- `backend/src/movie_companion/tmdb.py`: `TmdbMovieDetails` provider model and `map_tmdb_details(payload: dict[str, Any]) -> TmdbMovieDetails`.
- `backend/tests/test_tmdb.py`: a synthetic complete-record test; the assistant extends coverage after review.
- The existing fixture routes and UI continue to operate while this isolated slice is unfinished.

## Learner slice

- [x] Provide the provider model, mapper signature, and complete-record test.
- [x] Run `.venv/bin/pytest tests/test_tmdb.py -q` from `backend` and observe the intentional `NotImplementedError`.
- [x] Implement only `map_tmdb_details`, returning `TmdbMovieDetails` with the following mapping:

| External field | Provider model field | Transformation |
|---|---|---|
| id | id | Copy |
| title | title | Copy |
| release_date | year | Extract year and convert to integer |
| runtime | runtime_minutes | Copy |
| original_language | original_language | Preserve code |
| genres | genres | Extract each object's name |
| poster_path | poster_path | Preserve path |

- [x] Run the test and show the mapper for review.

## Assistant completion after review

- [x] Explain field renaming, list comprehensions, provider models, and validation.
- [x] Extend mapping tests for missing/empty dates, missing/zero runtime, empty genres, missing posters, and invalid identity. Unknown optional metadata remains `None`; malformed required identity is rejected. Verification: all 25 backend cases pass.
- [x] Specify and implement the next integration batch: server-side credential configuration, bounded HTTP calls, detail/credits composition, cache behavior, and synchronized Python/TypeScript contracts. Keep credential values out of chat, browser bundles, logs, and tests. Actual upstream verification requires a locally configured TMDB credential.
- [x] Preserve existing demo behavior and clearly identify the active data source. Provide safe poster placeholders and required TMDB attribution when showing live data.
- [x] Verify mapping/client failures with local fixtures before live requests, then run API/build/browser checks appropriate to the integration. Completed in `2026-10-08-tmdb-integration.md`.

## Sources checked

- Movie details: https://developer.themoviedb.org/reference/movie-details
- Image URL composition: https://developer.themoviedb.org/docs/image-basics
- Server-side bearer authentication: https://developer.themoviedb.org/docs/authentication-application

Actor resolution and typo search belong to the broader milestone and will be broken into subsequent pairing slices; they are not hidden requirements of this mapper exercise.
