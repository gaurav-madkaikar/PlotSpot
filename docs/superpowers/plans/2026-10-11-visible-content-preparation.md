# Visible content preparation and draft inspection

Execute inline in the existing checkout under the approved assistant-owned app integration scope.

**Goal:** Expose bounded RAG preparation progress and evidence-backed proposals on the movie page.

**Design:** A single-process local job service owns one active preparation job and shares the existing Ollama inference lock. Fixed reviewed movie IDs resolve to validated snapshots or the existing Wikipedia adapter; no client-supplied URLs/models/file paths. Persist each latest per-movie job checkpoint atomically under ignored private data. On restart active checkpoints become interrupted; do not silently resume. GET reads state, POST explicitly starts or cancels, repeated start while that same movie is active returns the current job. Latest finished job is readable after restart. Maximum eight batches/600 seconds, no automatic publication.

**UI:** A light collapsed Draft workspace panel beneath the spoiler control. Opening it and allowing spoilers reveals latest status; generation needs an explicit Prepare drafts click. Poll every two seconds only while active, cancel by exact job ID, keep safe errors local to the panel. Show stage, counts and all completed proposals with acceptance/retention status, quiz choices, reviewer reasons and expandable source excerpts. Never render raw model HTML, unvalidated external links or rejected content as the saved quiz.

**Files:** new preparation_jobs.py and preparation_routes.py, integrate lifespan/router in main.py, add stage checkpoints in content_preparation.py; frontend Zod/API helpers, movie-preparation-panel.tsx, movie.tsx and styles.css; backend service/route tests and browser journeys.

## Tasks

- [x] Implement durable latest-job state, atomic checkpoints, shared inference lock, bounded worker/cancellation/shutdown/interrupted recovery and safe projection of draft/source records.
- [x] Add strict spoiler-gated status/start/cancel routes and lifespan integration. Verify reuse/no generation on reads, wrong job cancellation, errors, persistence and no publication.
- [x] Implement accessible light panel, job polling, explicit start/cancel, proposal/evidence inspection, isolated errors and identity checks.
- [x] Run backend tests, production build and focused browser journeys for idle/start/progress/rejected drafts/cancel/reload/spoiler-off/unsupported states. Verify live panel and restore local servers.
- [x] Write lesson 42 and progress notes explaining requests, background tasks, checkpoints, polling and local single-worker limitations.

## Completion evidence

590 backend checks, 55 browser journeys and build passed. Real local API job completed one batch and cancelled with four inspectable proposals and unchanged saved facts/quiz fingerprints. Live light panel verified, servers restored, lesson 42 saved. No publication endpoint or hosted multi-worker claim.
