# 63. Durable research and reviewed shared content

The movie page reads a saved collection. Research now runs as a separate, durable
job; an explicit operator review selects what may join that shared collection.
Opening a film, taking a quiz or replaying it does not run these models.

## Follow the request

1. `POST /api/movies/{id}/preparation` requires spoiler consent. With a complete
   saved bank and no `refresh`, it returns a `ready` job without source/model calls.
2. With `refresh: true`, `ResearchPreparationJobs` admits one job to the existing
   SQLite queue. Duplicate active requests return the same job ID. A worker lease
   fences stale writers; the local model slot also coordinates with Discuss.
3. Wikipedia story research and registered publisher background reads overlap.
   A failed branch preserves successful evidence from the other branch. Sources
   are registered by code, rather than URLs invented by the model. Missing publisher
   snapshots can fall back to registered Wikipedia production sections.
4. RAG retrieves purpose-specific evidence. `build_plan` freezes at most eight
   tasks before writing. Local embedding/generation/review calls run serially.
5. A task writes at most two proposals, runs its domain critic, checks readiness,
   then checkpoints its **complete** result. An interrupted in-flight task can run
   again; already completed tasks are validated and skipped on restart.
6. The terminal result is an internal review report. The movie page continues
   serving the previous published bank. No consumer draft workspace is shown.
7. The operator exports the report, reviews sources/choices/novelty, and supplies
   a selection pinned to its hash. The CLI revalidates it, appends selected items,
   and commits the shared bank and audit receipt atomically.

Start at `backend/src/movie_companion/research_jobs.py`, then follow
`research_workflow.py`, `research_generation.py`, `research_checkpoint.py` and
`research_publication.py`. `main.py` wires the new worker into app startup;
`preparation_routes.py` adds the explicit refresh option. The frontend preparation
contract accepts only the registered Wikipedia/TIME/BFI provenance URLs.

## How the writer avoids repeating the bank

The writer receives the existing questions **and their correct answers**, existing
fact bodies, and earlier retained drafts. For example, an existing question asking
why Jade leaves camp prevents a new question asking what motivates the same
departure. A question asking where she goes could test a different detail.

Before calling Ollama, code extracts complete sentences from the retrieved units
and assigns `S1`, `S2`, etc. The model returns a support ID and content, not its own
citation URL or guessed quotation. Code resolves the ID back to the exact source
sentence. Unknown IDs and role mixing fail validation. Empty proposals are valid
when the available sentences contain no useful unused detail.

This is RAG: retrieve evidence, put it and saved topics into context, generate
bounded content, then verify. A vector score helps select context; it does not
prove truth, novelty or permission to publish.

## Critic, readiness and publication are different

The quiz critic assesses source support, every answer option and plausibility.
Code derives accept/reject/uncertain from its typed assessment. Facts have their
own semantic assessment plus source-local name checks. On resume/publication we
reconstruct these assessments and recompute decisions; a stored `accept` string
cannot override an assessment saying the selected answer is contradicted.

Readiness additionally checks quiz novelty/wording and the **selected citation's**
complete support for facts, including explicit purposes. Exact duplicate stems
and a small set of clear question/property distinctions are checked in code.
Unrecognized forms still need model review. These are bounded English rules,
not a universal semantic or grammar engine. Model judgements remain fallible.

Publication requires an explicit selection and source/topic review. Its review
kind records whether that review was human or assistant performed. An AI review
must never be recorded as a human review. There is no public publication endpoint,
and an agent has no tool that can call the operator publisher.

## Why checkpoint hashes matter

A report freezes movie identity, source revisions/content, the base bank, model
digests, task evidence and workflow implementation. Resume validates all of them
and reconstructs retained selections without rerunning completed inference.
If the bank or policy changed, the job is interrupted; start a fresh preparation.

The hash covers critic dependencies as well as orchestration. Otherwise changing
a nested critic prompt could silently reuse reviews produced under the old rule.
Hashes detect identity changes; they do not make a model's semantic opinion true.

## What happens during failures

- The whole operation, including source reads, has a 600-second deadline. Each
  model task has a 180-second deadline. There are no automatic inference retries.
- Expected task failures produce a bounded failure record and leave earlier
  completed work available. Cancellation propagates and preserves checkpoints.
- Graceful worker shutdown queues unfinished work for restart. The queue allows
  at most three recovery attempts; expired owners cannot write checkpoints.
- Publication validates the merged minimum of five facts/ten scored questions,
  capacity limits, citations and unique IDs/options. Selecting too little for a
  new bank fails even when the individual candidates look good.
- A compare-and-swap rejects a bank changed since review. The previous bank stays
  available while preparation runs or a rejected publication is attempted.
- Collection update and receipt insert share one SQLite transaction. A failed
  receipt insert rolls back the collection update. A crash after that transaction
  but before the job status update is recovered by retrying the same selection:
  its receipt reconciles the job without writing the bank twice.

The bank and queue use separate databases. This is an explicit receipt-based
recovery protocol, rather than a claim of one transaction across both databases.
A later refresh may replace the queue's latest job; historical publication receipts
remain in the content database.

## Measurements and their limits

The final 17 consumed development controls pass, including the three valid-question
failures from Lesson 62. The earlier Arrival drafts still yield zero ready items.
A smaller Llama reviewer matched 5/9 consumed quiz controls, so it was not adopted.

Six fresh fictional pairs were frozen before inference and labelled by an
independent AI reviewer blinded to model outputs. Four matched. The reviewer found
A NEW (different object locations), but the local model called it DUPLICATE; E NEW
(person met versus age), but the wording reviewer withheld it. Inputs, labels and
failed outputs are preserved. These are AI labels, not human labels; six cases
are insufficient for production qualification. The policy was not tuned against
these fresh failures.

Reports are under `evals/movie-rag/research/`: `readiness-v5-final.json`,
`quiz-review-llama-v1.json`, `fresh-topic-review.json`,
`fresh-topic-labels-ai-v1.json` and `fresh-topic-results-v1.json`.

## Live publication proof

The durable Arrival refresh completed eight tasks and sixteen proposals in
409.634 seconds, retaining two facts/five questions for review. No task failed;
the finite evidence budget ended before all requested new targets were reached.
The existing complete bank made the result reviewable without inventing filler.

Assistant source inspection selected `t1-Q1` (craft visited alone), `t2-F1`
(Ivanow's work influencing exterior dread) and `t5-Q1` (satellite phone). It withheld
four otherwise retained items: a question relying on uncited “follow suit” context,
a closely copied/generic vocal fact, a false Banks/China attribution in a mahjong
question, and a stem ambiguously locating recruitment rather than the craft.
The false attribution exposes a genuine automated critic failure, not just a
formatting issue. The reviewed publisher is necessary with the current model.

Explicit publication added one fact/two questions: Arrival has eight facts and
twelve scored questions. The API and movie UI both show them. The identical
selection retry used its receipt without another write. The other ten banks,
script policy and Inception expansion gate are unchanged. A recoverable private
bank backup and complete published-job archive are saved under `.cache/review`.

All 1,120 backend checks, 17 affected browser checks and the frontend build pass.
A separate live frontend-contract check accepts the Wikipedia/publisher job and
rejects a publisher lookalike URL. Resume, source/policy/bank changes, missing quotas,
transaction rollback, publication crash/retry, refresh races and duplicate starts
are covered by isolated-store tests. A new worker restart test skips a completed
research task. These checks do not constitute model or multi-user load qualification.

Artifacts: `arrival-reviewed-export-v1.json`, `arrival-reviewed-selection-v1.json`,
`arrival-publication-review-v1.json`, `arrival-publication-proof-v1.json` and
`live-durable-arrival-v1.json`. The proof preserves task assessments/readiness,
source/model/workflow hashes and the audit receipt. Publication was
`assistant_source_review`; no human approval or human-labelled accuracy is claimed.

The readiness evaluator's original frozen-bank replay now requires restoring the
private pre-publication bank to an isolated database via `--database`; the current
Arrival bank intentionally differs. Never overwrite the live bank to reproduce a
historical benchmark.

## Try the operator workflow

From `backend`, start a refresh explicitly through the local API. After it finishes:

```sh
.venv/bin/python scripts/review_research_job.py export \
  --movie-id 329865 --output ../.cache/review/arrival-review.json
```

Read the proposals, selected source sentences, options and existing movie bank.
Create a JSON selection containing `movie_id`, `job_id`, `report_sha256`, selected
`item_ids`, `reviewer`, `review_kind` (`human_source_review` or
`assistant_source_review`) and `reviewed_sources_and_novelty: true`. Copy job/hash
values from the export; do not fabricate an approval without reviewing.

```sh
.venv/bin/python scripts/review_research_job.py publish \
  --selection ../.cache/review/arrival-selection.json
```

The same selection is safe to retry. A different selection for an already
published job is rejected. Private caches, databases and local selection files
remain out of Git.

## Questions and answers

**Why not generate separately for each user?** The facts and story questions belong
to the movie and can be reused. User attempts/preferences are separate future
account data. Generation on every view would add latency and repeat identical work.

**Does passing all tests prove the model is good?** No. Tests exercise contracts,
cancellation, stale writes and failure paths with controlled model outputs. The
real-model reports measure particular cases. Independent wider data is still needed.

**Why are source reads parallel but model calls serial?** Source reads spend time
waiting for independent I/O. Multiple large local model calls compete for the same
machine resources. One admitted workflow makes current inference predictable;
this is not a distributed production-capacity guarantee.

**Why isn't a similarity threshold enough?** Similarity can confuse related but
different details, or miss paraphrases of the same detail. We compare the tested
fact, question and answer; even that reviewer failed two fresh cases, so publication
still requires explicit review.

**What is saved?** Sources/evidence, frozen task/review checkpoints, the shared
versioned facts/quiz bank and publication receipts. Read-only requests retrieve
published content. Draft generation needs an explicit refresh and publication
needs an explicit reviewed selection.
