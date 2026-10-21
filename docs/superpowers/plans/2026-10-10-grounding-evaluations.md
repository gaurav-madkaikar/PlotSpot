# Grounding Evaluation Implementation Plan

**Goal:** Establish a small development baseline before integrating generated answers into the app.

**Architecture:** Six authored fictional cases supply fixed evidence directly to the completed generation boundary, isolating prompt behavior from embedding/retrieval changes. A sequential local runner records replies, errors, timing, version hashes, automated checks, and pending human support review. Existing retrieval tests remain the separate scope checks. No tools, framework, app route, external inference, or prompt changes are added.

**Tech Stack:** Existing Python 3.12, HTTPX, pytest, local Ollama.

## Ownership and constraints

Assistant implements fixtures, runner, checks, report, and learning guide. Learner reviews case failures and edits their own prompt; do not make prompt changes for them. All six cases are development data, not a holdout. Automated substring/citation checks are smoke checks, not a supported-claim accuracy metric or universal injection defense. Report actual denominators, errors and abstention coverage. Record unavailable token metadata as null; do not fabricate it. All evidence is clearly fictional.

## Task 1 — fixture and grader

- [ ] Create `evals/grounding/cases.json` with two supported cases, one unsupported question, empty evidence, and two injected-source cases.
- [ ] Create `backend/src/movie_companion/grounding_eval.py`: `check_answer(case: dict, answer: GroundedAnswer) -> list[str]` reports status mismatch, incorrect expected citation set, absent required phrase groups, and forbidden marker leakage.
- [ ] Create `backend/tests/test_grounding_eval.py` verifying fixtures, every grader condition, and that keyword checks can still miss unsupported extra claims. Tests make no model calls.

## Task 2 — runner and learning checkpoint

- [ ] Create `backend/scripts/evaluate_grounding.py`. Fixed local client, existing model, one attempt per case, continue on HTTP/validation failures, write a structured report and exit nonzero on automated failures. `--output` lets the learner preserve baseline and comparison files. Attach runtime/prompt/dataset hashes and missing-token limitations.
- [ ] Run deterministic checks and one actual six-case local baseline. Preserve real outputs, failures, and counts. Do not change labels or prompt to make results pass.
- [ ] Create lesson 11 explaining unit tests versus evaluations, human review, development versus holdout, and a bounded prompt-edit exercise; update progress and evaluation README.

## Learner task

Preparation and baseline complete: all 136 backend tests pass. Local run produced 5/6 automated passes and zero generation errors. The costume reply was only `Silver`, missing recycled fabric; preserve this failure. Both injected cases passed their smoke checks, with human review still pending. Report saved as `evals/grounding/baseline.json`. The learner prompt was not modified.

Read baseline answers against evidence; revise only `build_grounded_prompt`, replacing the content-specific format illustration with a neutral schema and an abstention example, and improving labelled input sections. Run a comparison report. Investigate tradeoffs; if baseline already passes all automated cases, do not claim an improvement merely from rewording or lower latency in one run.
