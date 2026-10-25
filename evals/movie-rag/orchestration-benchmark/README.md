# Orchestration benchmark

This directory contains frozen comparisons between direct single-agent movie RAG, PlotSpot’s context-recovery/support-review pipeline, and a preregistered direct-first cascade.

- `holdout-v1.json` contains labels frozen before the first run.
- `run-v1.json` contains every answer, citation, retrieval trace, support verdict, Ollama call count, token count and latency.
- `comparison-v1.md` is the generated metric table.
- `blind-review-packet-v1.json` and `blind-review-form-v1.md` contain 24 randomized human-review tasks. Arm identities, automated labels and reference answers are absent. The decoding key stays under `.cache/` until review is complete.
- `holdout-v2-cascade.json` is a fresh 30-case holdout frozen before the cascade implementation or run.
- `cascade-preregistration-v1.json` fixes the routing triggers, metrics and adoption rule in advance.
- `run-v2-cascade-source.json` contains the direct and specialist executions on v2.
- `cascade-run-v1.json` and `cascade-comparison-v1.md` contain the composed cascade trace and comparison.

The result is 8/12 direct versus 9/12 specialist, with 3/3 missing-evidence controls passed by both. Specialist median latency is 2.72 times direct latency. This small, non-human-labelled set does not establish a statistically reliable quality improvement. One reviewer false positive remains.

On the untouched v2 holdout, direct passed 26/30, always-specialist passed 27/30, and the cascade passed 27/30. Cascade median latency was 4.785 seconds versus 10.221 seconds for always-specialist, with 41 versus 50 chat calls. All arms passed all eight missing/private-data controls. The cascade met its preregistered adoption rule, but it remains out of the live application pending the blinded human review and a larger external evaluation.

To complete the v1 human review, copy `blind-review-packet-v1.json` to a response file, fill every `review` object without opening the decoding key, then run:

```sh
cd backend
.venv/bin/python scripts/prepare_blind_rag_review.py score \
  --packet ../evals/movie-rag/orchestration-benchmark/blind-review-response-v1.json \
  --key ../.cache/orchestration-benchmark/blind-review-key-v1.json \
  --output ../evals/movie-rag/orchestration-benchmark/blind-review-result-v1.json
```

Do not overwrite v1 artifacts. New policies or reruns use new dataset and output versions. No benchmark command may publish movie content.
