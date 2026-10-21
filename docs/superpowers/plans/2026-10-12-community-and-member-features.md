# Community and member features implementation plan

**Goal:** Deliver movie discussions with owner controls and reporting/moderation, and require registration for Facts/Quiz/Discuss.

**Architecture:** Community contracts/store/routes use cookie-derived ownership and the existing SQLite account connection. A reusable member gate protects UI panels; API dependencies enforce access before evidence or model I/O. Plain-text community storage stays outside factual RAG.

**Tech Stack:** FastAPI/Pydantic, SQLite/Argon2 cookie sessions, React/TypeScript/Zod, existing Lucide/Button/Dialog and design tokens.

## Tasks

- [x] 1. Create backend community_contracts.py, community_store.py and community_routes.py. Add moderator UUID configuration and community rate limits. Verify domain/HTTP authorization, pagination, spoilers, CRUD, revision/idempotency and moderation using isolated accounts.
- [x] 2. Extend AccountBoundary to member paths, gate features/facts/quiz/questions/expansion/preparation and require CSRF on writes. Update existing test clients to explicit authenticated fixtures; keep independent guest/failure tests unmodified in policy.
- [x] 3. Add frontend community-contracts.ts/community-api.ts, member-feature-gate.tsx, movie-community-panel.tsx and community-post-form.tsx. Keep community opinion separate from the AI panel, plain text, owner-scoped capabilities, redaction and bounded forms/pagination. Add safe movie return paths and CSRF to AI mutations.
- [x] 4. Integrate movie-page member gates and community panel with existing warm light UI, mobile layout, accessible actions and delete confirmations. Guest metadata remains usable; no member fetches/AI calls until sign-in.
- [x] 5. Run full backend tests, frontend build and affected browser flows in disposable databases. Review scoped security/spec behavior, verify live guest gates without altering real posts/banks, update checklist/learning/configuration and restart the local API.

Verification: 1,199 backend tests pass; TypeScript/production build passes. The 105-case browser regression run exposed four stale legacy test-fixture expectations; all four were corrected and verified in the 12-case follow-up, including one added session-change case. Final five discussion browser checks pass after spacing/pagination polish. No shared bank/model policy changed; all eleven published-bank hashes match the preceding publication proof. Live API restarted and member UI inspected without posting to the real database.
