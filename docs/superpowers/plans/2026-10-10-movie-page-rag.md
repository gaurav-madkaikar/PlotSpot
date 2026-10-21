# Movie-Page RAG Pairing Integration Plan

**Goal:** Apply completed helpers in the actual movie-page question flow, with one learner-owned app pipeline function.

**Architecture:** Discuss tab contains a one-question form with cited response and source excerpts. POST `/api/movies/{movie_id}/questions` validates input and uses a bounded service: reviewed source mapping, spoiler permission before I/O, five-minute source cache, persistent document ingestion, eligible evidence, learner question pipeline, validated citations. Local Ollama model work is serialized; competing requests get a recoverable busy response. Source/embedding operations use fixed provider clients, deadlines and disk thread offloading.

**Tech Stack:** Existing FastAPI/Pydantic/HTTPX/Ollama/Chroma and React/TypeScript/Zod. Match the existing editorial design using ui-ux-pro-max guidance.

## Constraints and ownership

Assistant implements API, service safeguards, frontend and integration tests. Learner implements `answer_movie_question`: embed query, retrieve up to three passages, call grounded generation. Input passages are already movie/spoiler filtered; backend validates result citation membership again. This is the real endpoint's function, not another disconnected script. Keep it unfinished until learner implementation; UI returns a recoverable preparation error if invoked too early, never a fake answer.

Initial movie coverage is Interstellar, in both authored metadata/demo and live TMDB modes. Whole Wikipedia article is unclassified and requires explicit story permission, with no source fetch/model call when permission is absent. Other movies disclose unavailable sources. No community posting, news-feed claims, accounts, memory or autonomous tools are added.

## Tasks

- [x] Validate completed Wikipedia helper with all tests and real metadata fetch; record lesson 14 answers.
- [x] Add request/response schemas, source-backed question service, endpoint, thread offloading for disk storage, and learner pipeline seam. Bound 1000-character question, 180-second total deadline, fixed model tags, one active job, source cache TTL 300 seconds, and at most three final hits.
- [x] Build editorial question panel with visible label, explicit source/spoiler explanation, pending/cancel/error/abstention states, plain-text answer, revision links and source excerpts. Abort and erase results when movie/spoiler state changes; never reuse incompatible content or render HTML/model links.
- [x] Test API/service validation and source isolation with authored mocked providers; test UI submission, citations, loading/error and spoiler switching with controlled responses. Existing checks must still pass; learner pipeline checks are intentionally pending.
- [x] Explain the real UI→API→pipeline path in the pairing guide. No claim of working live movie answers until the learner function is complete and real end-to-end verification passes.

## Verification outcome

Assistant integration scaffolding is complete: 200 implemented backend checks, 18 browser journeys and production build pass. One learner-owned app-pipeline test remains intentionally red. Desktop/mobile mocked-answer views inspected. Real Wikipedia metadata fetch succeeded; real source-to-answer verification remains pending the learner function. No working live-answer claim is made.

## Learner implementation completed — 2026-10-10

Learner composed the endpoint pipeline; assistant corrected `k` and required `query_model` keyword arguments. All 201 backend checks pass. Real endpoint and unmocked browser generation produced the supported composer answer with revision links; missing personal evidence abstained. Lesson 15 and the compact smoke report record actual outcomes and limits. Expanded coverage/parallel agents remain separate milestones.
