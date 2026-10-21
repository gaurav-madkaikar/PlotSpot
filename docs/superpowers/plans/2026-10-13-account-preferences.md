# Account Preferences Implementation Plan

**Goal:** Persist two account settings and apply them to spoiler defaults and discovery.
**Architecture:** Dedicated SQLite preferences record read with sessions; CSRF-protected revision-checked PUT; existing AuthProvider broadcasts updates; query identities include adult mode.
**Tech Stack:** FastAPI/Pydantic/SQLite; React/TypeScript/Zod; pytest/Playwright.

## Constraints
Preserve current adult inclusion by default, member gates, shared movie/content records, original rating semantics and left-aligned light account design/dark footer. Work inline in the existing checkout; preserve unrelated work and use isolated test data.

- [x] Add Preferences model/store and migration, session contract/read/update route. Test defaults, persistence, owners, stale revisions, invalid writes and authorization.
- [x] Apply adult mode before local/live discovery pagination and suggestions; key snapshots by effective mode. Test changed-mode token resets and known-adult exclusion.
- [x] Add session/frontend contract, AuthProvider update and preferences panel. Wire spoiler default with current-visit override and discovery query/cache isolation. Verify save/conflict/error/reset/reload flows.
- [x] Run backend suite, frontend build and affected browser tests; inspect screenshot from isolated browser app. Preserve shared banks, update checklist and learning notes.
