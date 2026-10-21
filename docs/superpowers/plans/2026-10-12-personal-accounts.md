# Personal accounts implementation plan

> Execute inline against the approved existing account design and this scoped spec,
> using review checkpoints; no new worktree, commit or remote publication requested.

**Goal:** Deliver local accounts and owner-scoped durable personal collections while preserving guest browsing and shared movie content.

**Architecture:** Separate credential/session store from personal collection contracts/store and HTTP routes. React authenticates through opaque cookies and remounts its collection provider per owner; guest localStorage remains independent. Revision checks protect server writes and explicit imports.

**Tech Stack:** FastAPI/Pydantic, SQLite, argon2-cffi, React/TypeScript/Zod, existing CSS/Lucide, pytest/Playwright.

## Global constraints

Use the exact bounds, session/CSRF/Origin rules and exclusions in `docs/superpowers/specs/2026-10-12-personal-accounts-design.md`. Keep current movie banks and separate script policies unchanged. Reuse the existing light editorial design and named collections. No autonomous inference or content publication in account flows.

## Task 1: Credentials, sessions and collection contracts

Files: create `backend/src/movie_companion/accounts.py`, `personal_contracts.py`, `personal_store.py`; tests `backend/tests/test_accounts.py`, `test_personal_store.py`; modify backend dependency/lock.

- [x] Implement `AccountStore.register(username,password,previous)`, `login(...)`, `session(token)`, `bootstrap(token)`, `revoke(token)`; return typed session envelopes and raw cookie only at the boundary. Store hashed tokens and Argon2 hashes. Validate configuration and throttle before expensive work.
- [x] Implement `PersonalStore.load(owner)`, `replace(owner,snapshot)`, `import_browser(owner,request)` with owner-scoped revision CAS. Validate normalized collection names/IDs and subset/default membership.
- [x] Exercise password mismatch/unknown username, cookie rotation, expiry and rate limits; two owners must read/write independent state. Reopen DB and retry import to prove persistence and deduplication.

## Task 2: HTTP boundary

Files: create `backend/src/movie_companion/account_routes.py`; modify `main.py`; tests `backend/tests/test_account_routes.py`; extend `.env.example`.

- [x] Wire store at lifespan startup and a dependency for isolated tests. Add session/register/login/logout and collection GET/PUT/import routes.
- [x] Require authenticated session for personal routes; never accept owner IDs in bodies. Require configured Origin, JSON and matching CSRF on unsafe calls.
- [x] Bound request size, prevent private caching and return validation errors without echoed credentials. Test unauthorized/spoofed owner, missing/wrong/cross-session CSRF, null/foreign Origin, stale writes and rejected oversized/form bodies.

## Task 3: Identity-aware frontend persistence

Files: create `frontend/src/lib/account-contracts.ts`, `account-api.ts`, `auth.tsx`, `collection-storage.ts`; modify `collection.tsx`, `main.tsx`, existing collection controls/pages and movie spoiler switch.

- [x] Add Zod session/personal contracts and same-origin credentialed API helpers. Keep CSRF in memory and session tokens out of JavaScript storage.
- [x] Bootstrap/check identity, broadcast changes without tokens, and clear/revalidate private state on session errors or account switches. Remount collection provider per owner.
- [x] Preserve guest storage; signed-in mutations await server success with busy/error feedback. Reject stale writes and load canonical state rather than overwriting a newer tab. Explicit import leaves guest data intact.
- [x] Convert synchronous collection callers to await operation results before closing dialogs/navigating. Disable edits while loading/saving; keep failed operations reviewable and retryable.

## Task 4: Account UI and end-to-end proof

Files: create `frontend/src/pages/account.tsx`, `frontend/e2e/accounts.spec.ts`; modify shell/styles; add design page note.

- [x] Add account route/navigation, labelled sign-in/create form, visible password toggle, password manager attributes, concise errors, signed-in account overview, import and sign-out. Preserve movie UI hierarchy and mobile width.
- [x] Browser journeys: guest unchanged, explicit import, authenticated save/create/rename/membership/reload, account switch/second browser isolation, expired/revoked sessions, conflict and network recovery. Mock identities only in failure-contract journeys; use real isolated backend for persistence/isolation proof.
- [x] Run full backend tests, frontend build and affected browser checks using disposable account databases. Restart the owned app; verify account entry in a temporary tab and save a screenshot while leaving user data untouched.

## Task 5: Review and learning

Files: create `docs/learning/64-personal-accounts.md`; update README/progress/checklist; preserve local runtime evidence under `.cache`.

- [x] Review credentials/session/ownership boundaries and asynchronous state races; fix concrete issues and rerun affected tests. Verify all shared banks/script policy remain unchanged.
- [x] Explain cookies versus localStorage, hashing versus encryption, CSRF, owner derivation, revisions, explicit import, account switching, actual validation and deployment limitations. Update progress only for measured/delivered work.

Completion: 1,146 backend checks (26 new), 22 affected browser journeys (eight
account journeys) and frontend build pass. Both scoped review axes resolved cookie/
read ordering, session recovery, normalized throttling, test isolation and malformed
header findings. Live anonymous API/UI proof is recorded locally; all eleven movie
banks and script/Inception gates are unchanged. No permanent user account was
created by the assistant. Lesson 64 documents delivery and deployment limits.
