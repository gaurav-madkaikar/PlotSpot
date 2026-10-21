# 42. Taking a background AI workflow into the app

The movie page now includes a collapsed **Draft workspace** beneath the spoiler control. Open it after allowing spoilers to inspect the latest preparation job. **Prepare drafts** starts new work; reading the page or opening the workspace does not trigger generation.

This panel shows draft preparation separately from the saved facts and quiz. There is no publish button in this increment because our measured semantic review is not reliable enough to approve generated content automatically.

## The requests and their roles

| Request | Purpose | Runs the model? |
|---|---|---|
| GET `/api/movies/{id}/preparation?allow_spoilers=true` | Read latest status and completed proposals | No |
| POST `/api/movies/{id}/preparation` | Explicitly start or reuse an active job | Yes, in a background task |
| POST `/api/movies/{id}/preparation/cancel` | Cancel the exact active job ID | Stops the coordinator |

Both POST bodies require a strict boolean `allow_spoilers`. Cancellation also requires the exact job ID. Requests cannot choose URLs, local paths, models, execution tools or publication permissions. Unregistered movie IDs cannot start preparation.

`preparation_routes.py` validates those requests. `PreparationJobs` owns task scheduling, the shared inference lock, state and atomic checkpoints. The normal preparation coordinator still handles RAG, branch generation, critique and source checks.

## How a background task differs from a long HTTP response

The start request saves an initial checkpoint and creates an `asyncio` task, then returns a 202 response. It does not keep the browser waiting for all eight batches. The backend task continues when the user navigates away.

The frontend asks for status every two seconds while an open, spoiler-enabled workspace shows a running job. It stops polling when the job finishes or the panel closes. React Query handles caching and request cancellation; Zod validates responses. The API client checks that job and source movie identities match the current page.

After a start/cancel response, outstanding status reads are cancelled before updating the query cache so an older response cannot replace that action's result. Turning spoilers off hides all draft material and disables reads. Request cancellation by the browser is different from cancelling preparation: only the explicit cancellation endpoint stops the background coordinator.

## What progress means

The displayed stages are evidence collection, retrieval, drafting and review. Generator and critic checkpoints update the visible stage before the corresponding model call. Drafting/review repeat across batches, so the interface also shows how many batches have completed.

Counts show retained draft targets: five facts and ten questions. They are not accuracy percentages. A retained draft means the existing checks/critic allowed it into the draft report, not that a human verified it or the app published it.

The inspector includes completed accepted, rejected and uncertain proposals with review reasons. Quiz choices label the **proposed answer**. Expand **Review & evidence** to see the actual retrieved passage and the validated Wikipedia revision link. The excerpt comes from the trusted input passage, not a model-generated claim pretending to be source text. Unknown-source proposals cannot receive a source link.

## Persistence and restarts

Latest per-movie job records are stored under `backend/data/private/preparation-jobs/`. The original coordinator report is retained inside the job checkpoint; the API returns a bounded projection for the UI. Files are written to a temporary sibling and atomically replaced after flushing. A failed replace preserves the last complete record.

Only the latest job for each registered movie is kept; **Prepare again** replaces that movie's previous draft workspace. The reviewed publication database is independent and is never opened by this service. Source snapshots and document embeddings have their own caches.

A normal application shutdown cancels the active task and saves a cancelled record. After an unexpected stop, a previously running checkpoint is marked **interrupted** when read after restart. It does not silently resume or spend more model calls. Completed batch output remains available.

## Cancellation and resource bounds

Only one preparation job can run in this local backend process. It acquires the same Ollama lock used by movie discussion/discovery. A repeated start for that active movie reuses the job; another movie or competing AI request receives a recoverable conflict.

Cancellation targets the job ID so an old page cannot cancel a newer replacement job. The service handles immediate cancellation before task startup without leaking the lock. The coordinator performs no automatic retries. The worker has a 600-second overall deadline and at most eight batches; the existing model/source calls retain their own timeouts.

Cancelling Python work stops subsequent coordinator calls. It does not prove immediate GPU cancellation inside Ollama, and an already-started storage thread may finish its current write. Completed batches are checkpointed; partially generated branches in the current unfinished batch are not independently saved.

## Local deployment boundary

This is a single-process local demo job service. Its asyncio lock is not a distributed lock, and file checkpoints are not a distributed queue. Do not deploy it with multiple backend workers and expect shared scheduling guarantees. A hosted application will need an authenticated operator workflow, a durable queue/worker and database-backed ownership/concurrency controls. Those are separate backend improvements.

## Questions and answers

**Why use polling rather than streaming?** Status updates are sparse and batch-oriented. Simple two-second polling is easy to inspect and works with ordinary HTTP requests. Streaming becomes useful if we need token-level progress, which this feature does not claim to provide.

**Does refreshing lose the job?** No. The latest checkpoint lives on the backend, and reopening the workspace reads it. Unsubmitted UI actions and an unfinished current branch are not durable checkpoints.

**Why are rejected proposals visible?** They explain what the model attempted and why the system withheld it. They are marked as drafts and kept outside the saved collection, making failures inspectable instead of disappearing.

**Does cancellation delete completed drafts?** No. It stops the coordinator and keeps the most recent completed batches. Starting a new job replaces that movie's latest workspace record.

**Why not automatically publish retained items?** Our earlier labelled evals and actual runs exposed incorrect critic approvals/rejections. Meeting a quota or obtaining an accept decision is not a sufficient publication gate.

## Verified result

The live Inception API smoke started a real local job, observed generation and review phases, then cancelled after the first completed batch. Four proposals remained inspectable: two retained fact drafts and two rejected story questions. A fresh GET matched the cancellation response, and fingerprints of the saved facts/quiz before and after preparation matched exactly. The precise trace is `evals/movie-rag/preparation-api-live-smoke.json`.

The light workspace was checked in the live browser with the real saved checkpoint. Backend checks cover job reuse, conflicts, immediate cancellation, shutdown, interrupted restart recovery, strict route inputs, safe source projection and atomic-write failures. Browser journeys cover explicit start, progress polling, cancellation, reloads, evidence inspection, movie identity, spoiler gating and mobile fit.

590 backend checks, all 55 browser journeys and the production build passed. The existing servers were restored with the new routes. Generation quality has not improved by adding this interface; it makes the existing behavior and failures visible. Reviewed movie collections remain separate.
