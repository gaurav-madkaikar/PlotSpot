# Durable Preparation Implementation Plan

> Execute inline under existing authorization using executing-plans; no delegation or publication.

**Goal:** Queue internal preparation and recover completed work after restarts without duplicate publication or consumer draft UI.

**Architecture:** SQLite queue/worker leases in a focused store; existing PreparationJobs owns local execution and shared Ollama slot. Content preparation validates and resumes pinned evidence/checkpoints. Three attempts, existing model deadlines, explicit review only.

**Tech Stack:** Existing sqlite3, asyncio, httpx, Pydantic, pytest and frontend Zod; no new dependencies.

## Constraints

Only registered movies. No publication. Preserve all ten banks, source snapshots and story/background policies. No consumer draft workspace. Existing spoiler consent. Three attempts per logical job; 600-second attempt budget. Worker lease 30 seconds, heartbeat every 5 seconds. SQLite coordination assumes a shared local filesystem and does not implement distributed GPU admission across machines.

### Task 1: Frozen resumable batches

Files: modify `backend/src/movie_companion/content_preparation.py`; create `backend/src/movie_companion/preparation_resume.py`; test `backend/tests/test_preparation_resume.py`.

- [x] Add policy/source fingerprints and an exact evidence plan to new checkpoints. `prepare_drafts(..., resume=None)` validates matching metadata, plan and completed batches before any model call; restores retained drafts only from deterministic replay of validated records.
- [x] Persist complete batches and skip them on resume. An in-flight batch repeats. Example assertion: `assert resumed['batches'] == uninterrupted['batches']`; reject changed source/sections/policy/review IDs or forged retention.
- [x] Run focused existing orchestration checks and new resume fault cases; preserve the no-resume model behavior.

### Task 2: SQLite queue and leases

Files: create `backend/src/movie_companion/preparation_job_store.py`; test `backend/tests/test_preparation_job_store.py`.

- [x] Implement enqueue/latest/claim/save/cancel/lease/recover/release with transaction-owned checks. Repeated enqueue returns the same active ID; expired owners cannot save. Example: `assert store.enqueue(record)['id'] == store.enqueue(other_record)['id']` for the same active movie.
- [x] Coordinate FIFO and three-attempt recovery across independent connections. Migrate valid legacy checkpoints without overwriting existing rows. Reject oversized/invalid records through the supplied projection validator.
- [x] Verify concurrency, fenced writes, active/queued cancellation, expiry, retry exhaustion, corrupt records and legacy isolation in temporary databases.

### Task 3: Service integration and recovery

Files: modify `backend/src/movie_companion/preparation_jobs.py`, `backend/src/movie_companion/main.py`, `frontend/src/lib/contracts.ts`, `frontend/src/components/movie-preparation-panel.tsx`; update `backend/tests/test_preparation_jobs.py`.

- [x] Start dispatcher on app lifespan. Queue behind other movies and a busy local inference slot. Heartbeat leader/job ownership; observe durable remote cancellation and stop after lease loss.
- [x] Pass persisted report to the real runner's resumable coordinator. Requeue on graceful shutdown, cancel only on explicit cancellation. Read status without starting inference.
- [x] Extend queued response enum/labels without mounting the draft panel. Verify queued/reused requests, failure, cancellation and restart on temporary storage. Existing route validation remains intact.

### Task 4: Final checks and learning

- [x] Run full backend suite and frontend build. Run bounded real-source resume smoke against local Ollama using a new inspection report and no publication. Confirm preserved saved rows/story policy.
- [x] Save production guidelines, lesson 54 and progress; record exact observed limits, automatic attempt budget, inference replay and deployment restrictions. Mark tasks complete only after verification.

Validation: 870 backend checks and frontend build pass. Isolated local qwen two-batch restart completes with the same ID and first batch preserved; final draft targets remain incomplete and no publication occurs. Saved content/story/background hashes are unchanged. See lesson 54 for limitations.
