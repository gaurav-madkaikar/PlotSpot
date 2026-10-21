# 70. Quiz and movie-page history

The account page now has **Recently viewed** and **Quiz history**. Entries are private to the signed-in account, newest first, and paginated. Movie visits and completed quiz rounds are separate resources; each can be cleared independently. Guests do not record either history.

## What is recorded?

A successful movie-page visit records the movie ID, a server-resolved title/poster and the recording time. Opening the same film again creates another visit. Switching between About, Facts, Quiz and Discuss within that page does not. Discovery tile fetching, API prefetch, failed page loads and feature inventory reads do not create events. Tracking starts with this feature; earlier browsing cannot be reconstructed.

A completed quiz records its movie, score, number of scored questions, round size, content version and completion time. Incomplete rounds stay in the current UI state. The account summary does not store or reveal question text, answer selections or explanations. Each Play again round gets a new ID. Adding new generated questions begins a new expanded round while retaining the answers already selected in the UI.

## The recording preference

**Save movie-page history** starts enabled and can be disabled in Viewing preferences. Change the switch and save the preferences. The frontend stops sending new visit events, and the backend rechecks the stored setting inside the recording transaction. Disabling does not erase existing history; Clear history is a separate action. Quiz history remains available independently.

Existing preferences survive the schema migration. A SQLite column with a true default is added to the private account database. Older clients that omit this field preserve its current value rather than silently re-enabling tracking.

## Why does a visit have a UUID?

A network response might be lost after the server already wrote the event. Retrying with a new ID would create a duplicate. Instead, the visit or quiz round retains one UUID and retries that same event. The server stores a fingerprint of its input:

- Same owner, kind, ID and input: return the existing entry.
- Same ID with different input: reject the request with 409.
- New ID: record a new visit or round.

This also handles React StrictMode's development effect replay. The movie hook retains the event ID across cancelled/restarted requests. The storage transaction rechecks the ID before inserting, including when concurrent requests race.

## Why calculate quiz scores on the backend?

A client can submit any number it wants, so the API does not accept a score. It accepts selected option indices and validates them against the published quiz. All question IDs must be present, extra IDs are rejected, and indices must be actual integers from 0 to 3. Interpretation questions remain unscored.

For example, a round with ten factual questions and one reflection can finish with **9 / 10**, even if the reflection differs from the suggested interpretation.

The request includes both `content_version` and `content_prepared_at`. Generation can expand a bank without changing its version label, so the publication timestamp also matters. A new round based on a changed bank is rejected rather than silently graded against different content. An already recorded round can be retried after a bank update: idempotency is checked before looking up the current bank. Historical scores therefore remain fixed.

## How the code connects

- `frontend/src/lib/use-movie-visit.ts`: records actual successful member page views and exposes a retry if recording fails.
- `frontend/src/lib/use-quiz-history.ts`: saves a completed round, preserves the round ID for retry and handles replay.
- `frontend/src/lib/history-api.ts`: Zod response validation and owner-aware requests.
- `frontend/src/components/account-history-panel.tsx`: history modes, film links, dates, scores, pagination and clear confirmation.
- `backend/src/movie_companion/history_routes.py`: authentication/CSRF, expected-owner check, trusted movie resolution and server-side grading.
- `backend/src/movie_companion/history_store.py`: private events, input fingerprints, atomic recording, pagination and independent clearing.

The expected-owner header is a guard, not authorization. The session cookie still determines the owner. If another tab changes accounts before a request is sent, the header must match the current session or the server rejects the mutation before writing. The frontend also verifies the owner returned in every response.

## Questions to revisit

**Is history AI memory?** No. These are explicit account features. The histories are not sent to Ollama, indexed in RAG or used to infer preferences.

**Why not record visits in the movie GET endpoint?** Many callers fetch movie details without actually visiting a page. Recording only a successful rendered page prevents prefetch and background API reads from polluting browsing history.

**Why preserve quiz answers when a save fails?** The round is already complete. Losing answers would force a replay. Retry resubmits the same event without duplicating a successful write whose response was lost.

**Why separate clear actions?** A viewer may want to clear browsing history while keeping quiz results, or vice versa. Clearing does not change collections or the recording preference.

**What is the pagination behavior?** History uses live newest-first pages, rather than frozen search snapshots. New events can move entries between pages; refresh to see changes made elsewhere.

## Validation

1,281 backend checks, 42 affected browser checks and the frontend production build passed. Tests cover persistence, strict inputs, backend scoring, interpretations, same-version publication changes, account isolation, missing/wrong CSRF, wrong-owner requests, duplicate retries, recording disablement, migration, pagination, independent clear controls, guest nontracking and layouts at 1440, 768 and 375 pixels. The running account page was inspected in the native browser. All 11 shared published movie banks retained their prior hashes; no new model/source-generation calls were needed.
