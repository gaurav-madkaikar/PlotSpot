# 37. Turning one model call into a bounded workflow

We now have a separate preparation command that reads a source document and accumulates draft content. It uses plain Python, HTTPX and Pydantic; no LangChain knowledge is needed.

## Data flow

1. Load a saved `SourceDocument`: movie identity, article revision, original text and classified sections.
2. `proposal_evidence.evidence_batches` selects complete sentence groups, at most 600 characters each. Plot sections supply story evidence; production, casting, filming, effects and music supply background evidence. Other sections are skipped.
3. Each excerpt receives a temporary alias (`P1` etc.) plus its movie/source identity, revision, section and original character offsets. `verify_origins` checks the text and section against the actual source before any generation call.
4. `prepare_drafts` calls the generator, then the independent critic. Only accepted drafts enter the retained list; rejected/uncertain items remain in the batch trace.
5. Check for overlapping wording or reused supporting quotations against earlier retained drafts. This is a conservative heuristic, not semantic duplicate detection.
6. Save an atomic JSON checkpoint after each batch. Stop at five fact drafts and ten question drafts, or stop incomplete when the evidence, batch budget, deadline or model validation prevents completion.

The generator proposes content; the critic judges it; deterministic code owns routing, call budgets, validation and stopping. Neither model receives tools or database write permissions. Using two calls is useful only if measured quality justifies the extra time; existing eval misses remain visible.

## Why source provenance matters

Previously, a caller could label a plot passage `background`; a critic then accepted a plot fact. The new workflow derives purpose from the saved section classification and rechecks it against the actual document. Changing an alias's purpose or its text now fails provenance validation.

This addresses routing mistakes, not all hallucinations. A casting or production paragraph can include story details, and local snapshots are not cryptographically authenticated publisher records. Exact quotes, section labels and model approval still do not prove every claim or answer. Keep the semantic critic and human review before publication.

## Run from the project root

```sh
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/prepare_content_drafts.py \
  --source-snapshot .cache/source-snapshots/27205.json \
  --report evals/movie-rag/preparation-inception-ollama.json \
  --max-batches 8 \
  --deadline-seconds 360
```

Defaults use `qwen3.5:9b` for generation and independent critique. Installed model digests are verified first. Calls use the fixed local Ollama endpoint with redirects disabled. Each batch contains up to two story and two background excerpts; at most eight batches means at most sixteen generator/critic calls. A rejected batch may require no critic call.

## How this connects to the UI

It does not replace the UI's saved collection yet. The existing movie Facts/Quiz endpoints read reviewed publications from SQLite. This command saves its own JSON report, with `publication_approved: false` and `saved_collection_changed: false`. Meeting the numeric target produces `needs_review`, not `published`.

This separation lets us inspect bad drafts and measure quality without degrading working movie pages. Viewer-facing preparation jobs, reliable resumption and publication gates are subsequent steps.

## Questions and answers

**Why batch the passages?** A long article can exceed a model's useful context and encourages mixing plot and background. Small batches keep the inputs inspectable and bound individual calls. Their trade-off is weaker cross-passage context; the model must abstain when a detail cannot be established.

**Why use `await` in a loop?** Each review needs the draft from its generator. Sequential calls also avoid competing inference requests on one local GPU. Later, independent branches can be evaluated in parallel against this baseline if hardware allows it.

**What happens when generation fails halfway?** Completed batches remain in the last checkpoint. The final report records an incomplete state and a sanitized error type. The workflow does not refill a quota with unchecked output. Cancellation still propagates. Checkpoints preserve progress but automatic resumption is not implemented.

**What is an atomic checkpoint?** Write a temporary file in the destination directory, flush it, then replace the report in one operation. A failed replacement preserves the old report. This avoids readers seeing half-written JSON; it is separate from the application's SQLite publication transaction.

**Are five facts and ten questions guaranteed?** They are targets, never a reason to invent details. Quality rejection, sparse evidence or duplicate drafts can leave the report incomplete. Even complete draft counts still require review.

**Is this a quality eval?** The automated tests verify workflow contracts and failure handling. A real local-model run gives actual draft observations. Neither establishes held-out semantic accuracy; that needs labelled independent cases and human assessment.

## Actual local run and its limitations

The Inception run used Qwen 3.5 9B for both separate calls and retained five fact drafts and five question drafts across six completed batches. It hit the 360-second deadline and returned `incomplete`; it did not meet the ten-question target or replace the reviewed collection. Exact inputs, rejected proposals, decisions and source offsets are preserved in `evals/movie-rag/preparation-inception-ollama.json`.

Manual inspection found two critic-approved weaknesses: the Syncopy producer/company fact is ordinary metadata, and another draft changed the source's “very useful” into “only useful,” adding an unsupported qualifier. These are recorded in `preparation-inception-manual-observations.json`. They show both product-quality and factual-support gaps; they are not an exhaustive score for the remaining drafts.

After that baseline, the coordinator gained an efficiency stop: when every remaining passage belongs to a purpose whose target is already filled, stop incomplete with `no_evidence_for_unmet_targets`. This avoids spending calls on more facts when no story evidence remains for missing questions. The preserved real report predates this stop; its observed 360-second timing must not be presented as a benchmark of the updated stopping behavior. The new stop is covered by a deterministic regression test.

Validation: 510 backend checks passed. UI unchanged in this stage. The next integration gate is broader independently labelled quality evaluation, including ordinary metadata, unsupported qualifiers and distractor plausibility, before automatic publication or viewer-facing preparation jobs.
