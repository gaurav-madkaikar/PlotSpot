# Account History Implementation Plan

**Goal:** Private completed-quiz and movie-page history with a recording preference.
**Architecture:** Separate SQLite event store and routes; server metadata validation and quiz scoring; UUID idempotency; session-derived owner; frontend recording effects and account history panels.
**Tech Stack:** FastAPI, strict Pydantic, SQLite, React, Zod, TanStack Query, pytest, Playwright.

Preserve shared banks, account isolation, preference revisions, global/per-movie spoiler semantics and the existing layout. Work inline in the authorized checkout without unrelated edits.

- [x] Add migration and strict history contracts/store with server-side validation, replay safety, pagination and independent clear operations. Integrate the recording flag with backwards-compatible preference writes.
- [x] Add private routes using existing session/CSRF guards, trusted movie resolution and saved-bank quiz grading. Test isolation, auth, replay, invalid/versioned requests, ordering and disabled recording.
- [x] Wire actual movie-page visit recording, completed round recording/retry/replay, account history UI and preference controls. Ensure guest/account transitions cannot cross owners.
- [x] Run full backend suite, build and affected browser flows on disposable data; inspect desktop/mobile UI, confirm live availability and unchanged shared banks, then save learning/checklist updates.
