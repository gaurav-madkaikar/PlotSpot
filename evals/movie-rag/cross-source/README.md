# Cross-source story checks

This folder separates verifier regression tests from real generation inspections.

`development.json` (8 cases), `reserved.json` (8 cases) and `adversarial.json` (4 cases) have fixed acceptance labels. The reserved set was initially unseen, but uses analogous relationships with changed characters/objects. All three sets are now consumed; subsequent runs are regression checks, not held-out generalization measurements.

The verifier tests support, draft conflicts, ambiguity, subjective answers, malformed/missing support, embedded instructions and fabricated disclosure. Thresholds: zero false approvals, zero errors and at least 75% useful acceptance **per partition**. These small synthetic cases do not establish production safety. The evaluator checks supplied candidates; it does not evaluate candidate generation or retrieval.

`outcome-v1.json` preserves the initial failures. Versioned regression reports record later policies, model digests, implementation/dataset hashes, decisions and durations. Archived policies preserve the code behind historical results.

`live-*.json` records actual local-model retrieval/generation using reviewed Wikipedia snapshots unless otherwise stated. No inspection run publishes questions. Count abstentions and errors when judging usefulness; passing verifier regressions does not imply successful real quiz generation.

From `backend`:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_story_gate.py \
  --report ../evals/movie-rag/cross-source/regression-report.json

PYTHONPATH=src .venv/bin/python scripts/inspect_story_rag.py \
  --movie-id 27205 --question "Why does Cobb accept Saito's offer?" \
  --source-snapshot ../.cache/source-snapshots/27205.json --quiz \
  --report ../evals/movie-rag/cross-source/inspection.json
```

The gate is bound to the evaluated implementation, imported implementation, model digest and registered movie IDs. Restart the backend after implementation edits. Script versions remain unverified as a whole even when a particular event passes corroboration. Full script text stays in ignored private data, not these reports.

The current evaluator also runs eight real-film development cases. Quiz activation additionally requires a matching successful generation inspection for the specific movie. See [real-film quiz quality](../story-quality/README.md) for current outcomes and the activation command; the older synthetic-only outcomes here do not qualify a movie for expansion.
