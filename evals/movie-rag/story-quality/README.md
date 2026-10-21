# Real-film quiz quality

These reports distinguish question generation from verifier accuracy. All observations here are development checks. They are not an independent held-out benchmark or a production-safety guarantee.

## Generation inspections

| Policy/run | Inception accepted | Matrix accepted | Attempt errors | Saved content changed |
| --- | ---: | ---: | ---: | --- |
| Original v8 baseline | 0 | 1 | Not separately recorded | No |
| Qualified v9 | 1 | 0 | 0 | No |

The v8 Matrix question asks where humanity founded its refuge, answering “underground.” The saved quiz already asks where free humans established their refuge, answering Zion. This is weak topic novelty even though the literal string duplicate check passed. Do not claim the revised system improved total acceptance or broad accuracy.

The final v9 inspection proposed six seeds across two films. One reached final review and was accepted: the fifty years Cobb and Mal experience in Limbo. Five were withheld. Inception took 86.69 seconds and Matrix 54.41 seconds on this local run; concurrent deterministic/browser checks ran during part of the inspection. These are individual observed durations, not a latency benchmark or an improvement claim.

Versioned inspection files preserve failed experiments, including group-versus-sentence selection, evidence-first seeds, hybrid script retrieval and source-ID/quote handling. Their implementation hashes differ. `inspection-v9-qualified.json` is the final qualifying inspection. `gate-v9.json` separately records the frozen verifier and real-film checks.

## Labelled real-film checks

`real-movie-cases.json` contains eight authored development expectations: four useful events, a draft-version conflict, a different account of the sky-blackening event, a wrong cause and two valid quiz options. It was written before changing the retrieval policy; the developer saw the labels while developing, so it is not held-out. Script excerpts are referenced by pinned version and scene-bounded offsets; full screenplay text stays in private caches.

The gate checks the new scene selector followed by the existing blind-option and cross-source reviewer. It also reruns the 20 consumed synthetic regression cases. Each partition requires zero false approvals/errors and at least 75% useful acceptance. Keep mismatches in the report rather than changing labels after observing a model response.

Final v9 gate: 27/28 labels matched, with zero false approvals and zero errors. All 20 synthetic labels matched; the real-film partition accepted three of four useful cases and withheld all four negatives. The remaining useful case, Yusuf's recruitment, was conservatively withheld because the supplied script scene only recommends him. Its original positive label and mismatch remain recorded.

Quiz availability requires both a passing gate and a matching error-free generation inspection with an accepted question for that movie. Passing synthetic checks alone does not enable expansion. Matrix’s old script currently gives insufficient useful generation coverage, so its saved quiz remains usable while script-assisted expansion stays unavailable.

## Reproduce locally

From `backend`, with the reviewed Wikipedia snapshots and private script caches already prepared:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_story_quiz.py \
  --report ../evals/movie-rag/story-quality/inspection-v9-qualified.json

PYTHONPATH=src .venv/bin/python scripts/evaluate_story_gate.py \
  --quiz-report ../evals/movie-rag/story-quality/inspection-v9-qualified.json \
  --report ../evals/movie-rag/story-quality/gate-v9.json --enable
```

Inspections never publish. The live app publishes only through the explicit Generate more action, retaining previous questions and facts atomically. New source coverage, larger real-film evaluations and background preparation remain necessary before claiming broad reliability.

## Live publication check

`live-publication-v9.json` records the actual Inception API request: HTTP 200 in 90.90 seconds, one new question, 10 → 11 saved items, original items preserved, unique IDs and unchanged facts. Fresh API reads and browser reload displayed the new question and correct-answer feedback. This is an operational development check, not a general latency or accuracy benchmark.
