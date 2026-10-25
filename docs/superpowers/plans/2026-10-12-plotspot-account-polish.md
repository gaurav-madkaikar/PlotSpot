# PlotSpot account polish implementation plan

**Goal:** Complete the five UI/account changes explicitly authorized in this turn.

**Architecture:** Retain React providers and cookie-derived private ownership. Replace guest localStorage with a module-local document cache. Add an isolated verification mail module and hashed verification state to AccountStore; registration returns a verification receipt rather than a signed session.

**Tech Stack:** React, TypeScript, native dialog, Lucide/SVG, FastAPI, SQLite, Argon2id, Python SMTP TLS.

## Global constraints

- Existing account ownership and movie banks must be preserved.
- Guest state clears on a full refresh.
- New accounts cannot sign in until email verification succeeds.
- Preview verification links are local-development-only and clearly labelled.
- No credentials, email addresses or verification tokens in logs or test artifacts.

## Tasks

- [x] 1. Update public identity to PlotSpot with a reel SVG/favicon. Remove header saved count and use Collections. Add explicit trailer dialog centering. Validate desktop/mobile bounding boxes and keyboard dismissal.
- [x] 2. Replace guest persistence with readCollection/writeCollection document-memory copies. Remove storage-event synchronization. Add sign-in prompts and update import copy. Test SPA survival, reload clearing, account persistence and owner isolation.
- [x] 3. Add validated emails, nullable legacy migration, random hashed expiring one-use links and authenticated-password resend. Implement explicit loopback preview and TLS SMTP transport. Require email at the registration route, preserve CSRF/session boundaries, and test failure/expiry/reuse/rate limits.
- [x] 4. Add email and verification states to account form/API contracts. Keep verification receipts separate from sessions. Verify via explicit user confirmation, then sign in; preserve guest state through same-document preview navigation.
- [x] 5. Run backend regressions, frontend build and affected browser journeys. Review scoped changes, update learning notes and checklist, restart local server with selected preview mode and verify live page.

Validation: 1,162 backend tests and frontend build passed. Thirty-nine browser checks passed in the final batch; the remaining actor-search test passed after waiting for actor results before changing filters. All 40 distinct affected journeys now have a passing latest result. Review corrections were rechecked. Eleven saved movie banks are unchanged. Live API restarted with local preview configuration. Temporary tabs, browser servers and disposable account databases were cleaned up.
