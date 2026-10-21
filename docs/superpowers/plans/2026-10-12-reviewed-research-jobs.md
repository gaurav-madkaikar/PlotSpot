# Reliable content and durable reviewed preparation

**Goal:** Improve unused-topic generation and readiness, run multi-source research
through durable preparation jobs, and atomically publish an explicitly reviewed
selection into the shared movie bank.

**Architecture:** Keep the existing SQLite queue/lease/slot. A new workflow freezes
source-scoped RAG tasks, supplies saved and retained topics to a bounded writer,
checks content and readiness, and checkpoints completed tasks. Resume validates
policy/source/model/bank identities and recomputes retention without rerunning
completed calls. An operator CLI revalidates a terminal report plus a pinned
selection; a content-store receipt makes publication retries idempotent.

**Alternatives:** Automatic publication based only on critic agreement is not
supported by the observed failures. Adding more reviewers indiscriminately raises
local latency. Compare existing local models for narrow topic/wording roles first,
keep source/contract checks in code and require reviewed publication.

**Constraints:** User authorized items 1–2 together and all implementation/checks.
No new consumer drafts, semantic discovery, account system or external posting.
Sources remain registered Wikipedia/publisher inputs; scripts retain their
separate qualification. Facts describe production; quizzes test objective story.
Existing complete banks remain served during preparation and failed publication.
At most eight tasks, two proposals per task, five retained facts/ten questions,
600-second workflow deadline, one admitted local model workflow and no unbounded
model retries. Final merged banks require at least five facts/ten scored questions.
No commit or worktree is required for this authorized existing-checkout task.

- [x] Freeze the current policies; compare the existing local models on unchanged
  development readiness cases. Resolve the known valid-question overblocking
  without accepting same-topic paraphrases. Create fresh blinded pairs before
  inference and obtain independent labels/review; report human versus AI review
  honestly. Do not convert consumed development cases into a holdout claim.
- [x] Add `research_generation.py`: source-bound sentence IDs, existing topics and
  prior accepted drafts in the writer context, objective questions and quote-only
  facts. Add a source-scoped plan that diversifies unused evidence through existing
  RAG. Test unknown IDs, quotas, role boundaries and saved-topic input propagation.
- [x] Add `research_workflow.py` and `research_checkpoint.py`: freeze tasks,
  checkpoint each complete generation/review, validate resume identities and replay
  selections. Expected failures retain completed work; cancellation propagates.
  Reuse a prepared collection unless refresh is explicitly requested.
- [x] Add `ResearchPreparationJobs` using the current durable worker infrastructure;
  wire it into app startup and add a bounded refresh option to the existing start
  contract. Preserve legacy job projection/resume compatibility; consumer drafts
  stay hidden. Test leases, duplicate starts, cancellation, restart, bank changes
  and source/policy mismatches.
- [x] Add `research_publication.py` and an operator CLI: pinned job/report/source/
  policy/bank selection, rejection of withheld/unknown IDs, full citation and bank
  validation, compare-and-swap, audit receipt and idempotent retry. No unauthenticated
  HTTP publication endpoint. Test missing quotas, stale selections, tampering,
  conflicting refresh, transactional failure and receipt replay on temporary banks.
- [x] Run full backend and affected API/browser checks, real Ollama quality and
  unused-topic workflow checks, restart the owned backend and verify API reuse/
  preparation/review/publication on isolated stores. Inspect a concrete eligible
  selection before any authorized shared-bank publication and verify its UI if
  published. Preserve other banks and separate script gates.
- [x] Record code/model/source/selection hashes, actual failures, independent labels,
  publication receipts and learning walkthrough in Lesson 63. Update checklist,
  README and progress to distinguish delivered wiring from production qualification.

**Review checkpoints:** Quality evidence → durable workflow → reviewed publication
and runtime proof. If model results regress, retain failed artifacts and change
the policy deliberately; never rewrite labels or claim universal safety.

**Completion evidence:** Lesson 63 and `evals/movie-rag/research/README.md`. Final
consumed controls 17/17; fresh independently AI-reviewed pairs 4/6, unchanged after
evaluation. Real durable Arrival run: eight tasks/sixteen proposals, two facts/five
questions retained; explicit assistant review published one fact/two questions.
Other ten banks/script gate unchanged; receipt replay is idempotent. 1,120 backend
checks, 17 affected browser checks and frontend build pass. Automatic semantic
publication and production quality/throughput remain unqualified.
