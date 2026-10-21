# 38. Measuring quality before accepting a prompt change

This stage adds an evaluation harness and a development regression gate. It does **not** make the existing critic reliable enough to publish movie content automatically.

## What we evaluate

The critic receives source passages and generated facts/questions, then returns accept, reject or uncertain. A labelled case supplies the expected decision and a failure category. We compare decisions, not exact reason wording or embedding similarity.

Example: a source says a technique was “very useful,” while a draft claims it was “only useful.” The expected decision is reject: the draft adds exclusivity that the source does not establish. A real supporting quotation does not make the entire claim correct.

Other cases cover ordinary metadata disguised as interesting trivia, plot in Facts, unusual craft details, invented numbers/causes, wrong answer indices, implausible or overlapping quiz choices, missing context, subjective symbolism and instructions inside evidence. These cases judge the critic's behavior; they do not measure retrieval quality or malicious tool execution.

## Dataset structure and split

`evals/movie-rag/content-quality-development.json` contains 18 labelled items in three batches. The first six preserve our earlier development cases. `content-quality-held-out.json` contains twelve reserved items in two batches, with different sources and case identities.

Each batch contains bounded evidence, strict `ContentProposals`, and exactly one label for every proposal. Missing/extra labels and duplicate identities fail before inference. The labels are authored expectations over fictional examples, not independently collected annotations or real-movie quality scores.

We recorded the original policy on development cases, tested a revised policy on the same cases, selected a policy using those results, and evaluated that frozen policy once on the reserved cases. No changes were made against reserved outcomes in this stage. Those cases have now been inspected: future tuning must treat them as regression/development cases and use a fresh reserved partition for another unseen evaluation.

## Why overall match rate is insufficient

The evaluator records counts and denominators separately:

| Metric | Meaning |
|---|---|
| Label matches | Exact expected decisions across all labelled items |
| Useful acceptance | Expected-accept items that were accepted |
| False acceptance | Expected-reject/uncertain items that were accepted |
| False rejection | Expected-accept items that were rejected |
| Uncertain | Items receiving an uncertain decision |
| Errors | Items without a valid judgement |

A critic that rejects every item might avoid false approvals while making the product useless. Useful acceptance exposes that trade-off. Rejecting an expected-uncertain item misses the exact label but still avoids an incorrect approval; these are different kinds of failure.

Malformed replies and timeouts remain in the denominator. When the overall deadline stops a run, unfinished items receive `error`, and the report is incomplete. `state: complete` means evaluation work finished, not that quality passed.

## Actual results

All runs used the verified local `qwen3.5:9b` artifact, temperature 0, seed 7, thinking disabled and at most 1,800 output tokens per critic call.

| Run | Label matches | Useful approvals | False approvals | Time |
|---|---:|---:|---:|---:|
| Original v1, development | 12/18 | 4/5 | 4/13 | 58.46 s |
| Candidate v2, development | 8/18 | 2/5 | 6/13 | 63.57 s |
| Selected v1, reserved | 6/12 | 3/4 | 4/8 | 43.25 s |

The longer candidate prompt regressed. More explicit instructions did not establish better behavior. We restored v1, verified its implementation fingerprint matched the original evaluated artifact, and preserved both policies under `evals/movie-rag/policies/` as non-executable text archives.

The development gate allows a candidate only if it does not increase false approvals, reduce useful approvals or reduce label matches, and has zero evaluation errors on the same cases. This is a relative regression check, **not** an absolute production-quality gate. A weak baseline can remain selected while both policies fail product requirements.

The reserved run exposed ordinary metadata approvals, poor distractor approval, invented context and a wrong-answer index. In the last case, the critic's reason described option zero as the station clerk even though option zero was actually the porter. The answer-selection mapping should be made explicit in subsequent structured verification. We have not tuned against that reserved observation here.

## How the code connects

- `content_quality_eval.py` validates datasets, calls the critic sequentially, preserves errors and computes metrics.
- `evaluate_content_quality.py` verifies the local model and writes atomic report checkpoints.
- `content_quality_comparison.py` verifies comparable dataset/model/settings fingerprints, selects the policy from development results and requires the reserved run to use that same frozen policy.
- `compare_content_quality.py` saves normalized metrics and all changed decisions. The old baseline's metric named `unsafe_acceptance` is normalized to `false_acceptance` from its unchanged case decisions; ordinary metadata is a quality error, not inherently a malicious action.

The reports retain source dataset fingerprints, model digest, policy version, implementation fingerprint, generation settings and batch latencies. The current helper does not return token counts, and these runs do not provide hardware-normalized performance benchmarks. Timing comes from one local observation per run.

## Run from the backend directory

```sh
.venv/bin/python scripts/evaluate_content_quality.py \
  --dataset ../evals/movie-rag/content-quality-development.json \
  --output ../evals/movie-rag/my-development-run.json
```

Choose a new output filename to preserve historical runs. The command evaluates the currently active critic; v2 is archived evidence of a rejected candidate, not the active policy.

The completed comparison is `evals/movie-rag/content-quality-comparison.json`. Production movie Facts/Quiz continue using reviewed SQLite publications; these evaluation commands never publish.

## Questions and answers

**Are evals tests with fixed outputs?** Here the fixed expectation is a behavioral decision, not fixed prose. Unit tests check the evaluator's plumbing with mock responses; model evals call actual Ollama and measure which labelled expectations hold.

**Why not similarity thresholds?** Similar wording can still change “sometimes” to “always” or attach the wrong answer index. Similarity measures closeness, not whether a statement is supported or a quiz has one correct choice.

**Why keep the worse candidate?** Its report and exact policy show a measured trade-off, prevent repeating it and make the rollback explainable. Recording only successful experiments would hide how the selection process works.

**Does this guarantee no malicious actions?** No. The critic has no tools or publication permissions, and injected evidence is treated as data. The quality suite does not test a permissioned tool executor. Future tool agents need separate authorization, action constraints and adversarial tool-use evals.

**What happens next?** Introduce structured checks for factual support, content suitability and answer/choice validity, with an explicit selected-answer value. Compare them against this baseline on development cases, then use fresh reserved cases. Automatic publication remains gated until the evidence supports it.
