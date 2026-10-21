# Bounded research development comparison

`cases.json` freezes ten assistant-authored operational scenarios. Each runs in
both modes; `operations-v1.json` passes 20/20 status/cleanup checks. Six paired
synthetic delayed-read runs alternate mode order and show identical sources.
The 37.296 ms versus 20.671 ms medians include injected 15/20 ms waits, not real
internet latency or production throughput.

`arrival-cached-v1.json` runs the real existing Ollama RAG/writer/critic modules
with frozen Wikipedia, TIME and BFI caches. Source inputs and inspected outputs
are identical across modes. Cached acquisition takes 10.477 ms sequential and
19.546 ms parallel; total inspection takes 118.141s versus 63.990s. Index/model
warm-up confounds total time. No total speedup is attributed to parallelism.
These are specialist read-only research branches, not autonomous browsing agents.
Local model calls remain serial inside one inspection, without global admission.

`inspection-v1.json` records source review and preservation. Both quiz drafts
repeat saved topics, one has awkward wording, and two eligible fact drafts have
selected quotes that omit parts of their claims. Generic titles also survive
critic acceptance. Another fact is withheld as a saved-wording duplicate.
Six proposals are unpublished; eligibility is not semantic truth or publication.
All eleven saved banks, script policy and Inception expansion gate are preserved.

Source text/caches/vectors stay private. Reports retain bounded generated context
and provenance. Initial/final module hashes match; the operational labels were
not changed after outputs. No independent semantic holdout, safety qualification,
new movie-page feature or token/cost benchmark is claimed. Existing HTTP jobs
remain Wikipedia-only; this slice exposes an internal CLI workflow.

From backend, use new report paths and the existing local reviewed model tags:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_movie_research.py --output ../evals/movie-rag/research/operations-new-run.json
PYTHONPATH=src .venv/bin/python scripts/inspect_movie_research.py --movie-id 329865 --compare --report ../evals/movie-rag/research/arrival-new-run.json
```

`--order parallel-first` reverses the real execution order. Evaluated module files
must stay unchanged while inference runs. The tool does not fetch new sources,
write source caches or publish content. [Lesson 61](../../../docs/learning/61-parallel-research.md)
explains asyncio, failures, source contracts and the complete request flow.

## Content readiness and retained model failures (Lesson 62)

`readiness-baseline-v1/` preserves the Lesson 61 inspector/CLI. Its frozen Arrival
proposals are replayed against the original source and saved-bank digests.
`readiness-cases.json` freezes fourteen fictional cases; `readiness-cases-v2.json`
preserves every original label and adds three positive cases before v2 execution.

- `readiness-v1.json`: 13/14 controls; accepted an awkward stem and replayed fact's
  unstated narrative purpose. Source retained in `readiness-policy-v1/`.
- `readiness-v2.json`: 14/17 controls; purpose repaired, but combined topic/wording
  prompting regressed and one response failed schema validation. Source retained
  in `readiness-policy-v2/`.
- `readiness-v3.json`: 14/17 controls with separate topic/wording reviews. The three
  failures wrongly withhold valid new questions (age, distinct objects with the
  same color, and a future-need reason). All eight fact controls match.

Final replay withholds both previously eligible quiz questions and both facts.
Readiness cannot override earlier necessary rejection. Quote provenance, narrow
source-local names/title/stem rules, topic match-ID checks and bounded explicit
purpose routing are enforced in code. Meaning/wording judgements remain fallible.
None of the six original drafts is published; ready is an inspection observation.
Existing public script/quiz policies and movie-page behavior remain separate.

From backend, with the original private bank manifest and unchanged caches:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_content_readiness.py --output ../evals/movie-rag/research/readiness-new-run.json
PYTHONPATH=src .venv/bin/python scripts/inspect_movie_research.py --movie-id 329865 --mode parallel --report ../evals/movie-rag/research/arrival-readiness-new-run.json
```

Use new report paths. The evaluator preserves partial/failing reports and exits
nonzero for unmatched controls. Existing response adapters do not retain token
usage. Module/model/source/bank fingerprints distinguish iterations; historical
outputs are not claims about later source files. No independent holdout or
production safety/quality qualification follows. [Lesson 62](../../../docs/learning/62-content-readiness.md)
explains the decisions, examples and observed failures.

`arrival-readiness-v3.json` verifies the complete real flow with the layer enabled:
both branches inspect successfully in 107.401s, with the same generated proposals
as Lesson 61 and zero newly ready items. `readiness-inspection-v3.json` retains
source assessment, the three overblocking controls and preservation checks.
All eleven banks, script fingerprint and Inception expansion gate are unchanged.
Final module hashes match both final reports. Single-run duration includes added
reviews and is not a production speed comparison.

## Durable reviewed research (Lesson 63)

- `readiness-policy-v3/` preserves the previous rules. `quiz-review-llama-v1.json`
  matches 5/9 consumed quiz development cases; the smaller model was not adopted.
- `readiness-v5-final.json`: 17/17 consumed development controls in 98.193s, all
  original Arrival drafts still withheld, code/bank unchanged during evaluation.
  This is regression repair, not held-out accuracy.
- `fresh-topic-review.json` freezes six pairs before inference. Separate
  `fresh-topic-labels-ai-v1.json` contains blinded independent **AI** labels.
  `fresh-topic-results-v1.json` matches 4/6. A wrongly reports duplicate; E is
  withheld as unclear. The policy was not tuned after this fresh evaluation.
- `live-durable-arrival-v1.json`: consent rejection, inference-free reuse,
  duplicate-start identity, live checkpoints and unchanged banks during preparation.
  Eight tasks/sixteen proposals complete in 409.634s without task errors; finite
  evidence exhaustion retains two facts/five questions for review. This is one
  local run, not a production latency/quality comparison.
- `arrival-reviewed-export-v1.json`: seven retained candidates plus all proposals.
  `arrival-publication-review-v1.json` records explicit assistant source inspection.
  Four retained items are withheld, including a false Banks/China attribution that
  the automated critic accepted. `arrival-reviewed-selection-v1.json` pins the
  three selected items, exact original report hash and assistant review provenance.
- `arrival-publication-proof-v1.json`: complete task assessment/readiness records,
  source/model/workflow hashes, committed audit receipt, identical retry replay,
  HTTP counts (eight facts/twelve questions), other-ten-bank preservation and
  unchanged script/Inception policies. The actual bank/job databases and recoverable
  pre-publication backup remain private, outside Git.

Use the operator CLI in [Lesson 63](../../../docs/learning/63-reviewed-research-jobs.md).
Publication needs explicit source/novelty review. No human labels or human review
are claimed for this run. The automated failures remain visible; wider independent
quality, safety and throughput qualification is pending.

The old readiness replay pins the pre-publication Arrival bank. To reproduce it,
use a private isolated copy of that backup with `--database`; the current live bank
was intentionally extended and its stale-bank check should reject the old run.
Do not overwrite current published data to replay a historical benchmark.
