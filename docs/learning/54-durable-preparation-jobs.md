# 54. Durable preparation jobs and restart recovery

A task created with `asyncio.create_task()` lives inside the current Python process. Saving some JSON does not make that task survive a crash. We now separate the durable job from the process temporarily executing it.

## Request, queue and worker

`PreparationJobStore` stores internal movie-preparation requests in SQLite. A repeated request for a queued/running movie returns the existing job ID. Other movies queue in request order rather than receiving a busy error. The dispatcher also waits while the shared local Ollama slot is busy with a discussion or quiz request.

`PreparationJobs.open()` starts the dispatcher during application startup. Status reads inspect saved state; they do not start model calls. The consumer pages still have no draft workspace, and these internal jobs cannot publish facts or quizzes.

The queue uses one current record per registered movie. Explicitly starting a terminal job creates a new ID. It is not a full historical job-audit database or a queue for all TMDB films.

## Ownership expires unless renewed

Two API processes might see the same pending request. SQLite transactions elect one worker through a 30-second lease: permission to execute until a recorded expiry. Heartbeats renew that permission, normally every five seconds during active work.

A job also records its owner and expiry. Every checkpoint write verifies the job ID, active state, owner, job expiry and worker lease. If another worker takes over, the old worker cannot overwrite its checkpoints. This is called fencing.

An expired running job returns to the queue with its last saved report. A job gets at most three execution attempts before repeated interruptions leave it interrupted. Model/validation failures finish incomplete or failed; they do not enter an unlimited retry loop. Graceful shutdown requeues current work; explicit cancellation leaves it cancelled. Another process can request cancellation durably, and the owning dispatcher observes it.

## What resuming actually means

`prepare_drafts(..., resume=report)` first checks the source body and sections, model identities, reviewer identity, workflow fingerprint, budgets and frozen evidence plan. It then validates each completed batch and recomputes the retained-item selection. Saved selections and retained lists must match that replay.

Only a complete generator/reviewer batch is checkpointed as finished. On restart, those completed batches are skipped. A batch interrupted during generation or review can run again. This gives **at-least-once inference**, not exactly-once LLM execution; the retained completed batches are not duplicated.

Frozen RAG evidence is reused without retrieving a new plan. If the source or policy changes, the job stops interrupted instead of mixing versions. Legacy JSON jobs lack these resume guarantees: valid old reports migrate into SQLite, while old running jobs become interrupted and require a fresh start. Original JSON files stay intact.

Each execution attempt keeps the existing bounded preparation deadline. Three attempts can consume up to three such budgets; the total generation work is not unlimited.

## Why these checks are different from factual evals

The new checks deliberately simulate restarts, concurrent enqueue, lease expiry, stale writes, cancellation races, source changes and malformed checkpoints. They test orchestration reliability. They do not establish that a generated movie fact is true or a quiz is interesting. Those remain separate model/source evaluations and inspected publication gates.

Checkpoint validation checks internal consistency against pinned code and evidence. It does not cryptographically authenticate model judgments or protect against an attacker who controls our private database/filesystem. Clients cannot submit resume reports through the preparation endpoint.

## Questions and answers

**Why keep SQLite rather than only an in-memory queue?** Its transactions preserve requests and coordinate claims across processes after the original process disappears.

**Why not immediately resume every old JSON file?** Old files lack a frozen evidence plan and matching workflow identity. Resuming them would assume facts we cannot validate.

**What happens when the model server is busy?** Jobs stay queued while the shared local slot is occupied. An actual model/provider failure finishes with a bounded error state.

**Can the same LLM call happen twice after a crash?** Yes. If it finished remotely but its reviewed batch was not durably saved, the replacement worker may repeat it. Completed saved batches are skipped.

**Can a completed job publish content automatically?** No. Draft completion and publication are separate. Existing saved content remains readable throughout preparation.

**Is this ready for workers on multiple machines?** This implementation coordinates processes sharing one SQLite file on a supported local filesystem. Separate machines, distributed GPU admission, accounts and production traffic require additional infrastructure and load testing. The local shared Ollama lock is process-local; the database lease coordinates preparation workers, not discussion requests across separate API processes.

## Observed verification

All 870 backend checks and the frontend production build pass. Thirty-three additional checks cover queue ownership/concurrency, cancellation, recovery limits and resume validation. Existing busy-job/shutdown assertions were updated to the new queued behavior.

The real local qwen3.5:9b inspection used two fixed Inception evidence batches and a temporary SQLite database. After batch one, graceful shutdown left the job queued. A new manager resumed the same ID, preserved batch one byte-for-byte as JSON data, and completed batch two. It retained four fact drafts/two question drafts and stopped at the two-batch budget, so the final content state was incomplete. That is successful recovery, not successful completion of a publishable content bank. The resumed attempt took 32.08 seconds. Report: `evals/movie-rag/preparation-recovery-local-v1.json`.

No generated content was published; hashes confirm the ten saved banks, story policy and background policy were unchanged. Actual abrupt crash/lease expiry is tested with isolated clocks and separate database connections; this model smoke uses graceful shutdown, not SIGKILL. It does not exercise full RAG retrieval, independently evaluate semantics or establish production throughput.

After restarting the local backend, health and internal preparation-status reads returned successfully. Repeated Inception/Arrival fact and quiz reads were identical and ready. All ten saved SQLite rows remained unchanged. Live check: `evals/movie-rag/preparation-recovery-live.json`.
