# Foundation Implementation Plan

> Execution: inline pair implementation, as selected by the user. Explain decisions and stop at the learning checkpoint after this milestone. No implementation delegation.

**Goal:** Deliver a runnable movie discovery/detail foundation without pretending that agents or live sources exist.

**Architecture:** FastAPI validates authored demo records and owns simple search/filtering. React consumes a runtime-validated contract through a narrow API client. Browser-only collection/spoiler state is explicitly temporary.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, HTTPX/pytest; React, TypeScript, Vite, Tailwind, Radix-backed shadcn-style primitives, TanStack Query, Zod, React Router, Playwright.

## Global constraints

- Local-first; servers bind to 127.0.0.1.
- No real agents, AI-generated sample answers, credentials, or remote data requests.
- Original illustrated covers; do not label them official posters.
- Dark charcoal/warm white/amber design tokens; visible focus and reduced motion.
- Future movie features expose honest availability states.
- Introduce evaluation structure now; labeled per-agent cases precede each agent.

## Task 1 — backend boundary

Create `backend/pyproject.toml`, `backend/src/movie_companion/{main,schemas,catalog}.py`, `backend/src/movie_companion/data/movies.json`, and `backend/tests/test_api.py`.

Produces: GET `/api/health`; GET `/api/search?q=&genre=&max_runtime=` returning `MovieSearchResponse`; GET `/api/movies/{movie_id}` returning `Movie`. Empty/whitespace queries list the collection; unknown film IDs return 404; oversized query and invalid runtime return 422. Search is case-insensitive substring matching over title/cast, not fuzzy or semantic matching.

- [x] Create the typed schemas, fixture repository, and routes.
- [x] Verify actor matching, combined filters, invalid inputs, unknown IDs, and truthful data-source flags with pytest.
- [x] Install locally and lock dependencies.

## Task 2 — product foundation

Create frontend configs and `src` modules for contracts/client, browser collection, shared UI, routes, and pages.

Consumes: backend movie/search responses. Produces: `/`, `/movies/:movieId`, `/collection`, and `/about`. Search/filter state lives in the URL; back navigation restores it. Abort superseded requests. Movie saves persist in this browser. Spoiler controls store a per-film prototype preference; future sections do not generate content.

- [x] Implement semantic theme tokens and original cover assets.
- [x] Build discovery, movie detail, collection, and about routes.
- [x] Add loading, API failure/retry, empty search, unknown movie, and corrupt-storage recovery behavior.
- [x] Build with strict TypeScript.

## Task 3 — verification and learning

Create `frontend/e2e/foundation.spec.ts`, Playwright config, `docs/learning/01-foundation.md`, `evals/README.md`, and CI checks.

- [x] Verify search/detail/back-state, browser-local saving/reload/removal, keyboard tab behavior, unavailable features, invalid routes, and mobile overflow.
- [x] Inspect desktop/mobile screenshots and reduced-motion behavior.
- [x] Run backend tests, production build, and browser tests.
- [x] Record actual results and provide a small learner exercise before milestone 2.

The approval in conversation covers this design and implementation; no additional design approval round is required.
