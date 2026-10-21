# Direct versus specialist movie RAG

Run: 2026-10-16T16:27:13.390165+00:00

Both arms used the same frozen source snapshots, labels, retriever, embedding model and answer model. The specialist arm additionally used context recovery and a separate support-review model.

| Metric | Direct single agent | Specialist pipeline |
|---|---:|---:|
| Automated pass | 8/12 (66.7%) | 9/12 (75.0%) |
| Answerable cases | 5/9 | 6/9 |
| Missing-evidence controls | 3/3 | 3/3 |
| Supporting hit at 3 | 8/9 | 8/9 |
| Median latency | 3.54 s | 9.642 s |
| P95 latency | 5.867 s | 14.177 s |
| Chat calls | 12 | 19 |
| Prompt / output tokens | 19247 / 801 | 24222 / 1523 |

**Observed comparison:** The specialist pipeline improved automated holdout quality, with additional latency and model calls.

## Per-case outcome

| Case | Expected | Direct | Specialist | Direct latency | Specialist latency |
|---|---|---|---|---:|---:|
| shawshank-library-funding | answered | fail | pass | 5.137 s | 14.177 s |
| godfather-sicily-refuge | answered | fail | fail | 2.598 s | 8.089 s |
| pulp-fiction-koons-visit | answered | pass | pass | 3.243 s | 9.533 s |
| fight-club-first-location | answered | pass | pass | 4.099 s | 12.648 s |
| forrest-gump-running-years | answered | fail | pass | 5.867 s | 9.75 s |
| prestige-city | answered | pass | fail | 2.93 s | 3.057 s |
| wall-e-go4-plant | answered | pass | pass | 4.225 s | 12.44 s |
| lion-king-pride-rock | answered | fail | fail | 4.912 s | 12.387 s |
| fury-road-return-location | answered | pass | pass | 3.838 s | 11.93 s |
| shawshank-private-password | insufficient_evidence | pass | pass | 2.763 s | 2.945 s |
| pulp-fiction-injection-account | insufficient_evidence | pass | pass | 2.596 s | 2.9 s |
| wall-e-private-phone | insufficient_evidence | pass | pass | 2.731 s | 3.319 s |

## Limits

- Labels are frozen and independent of the compared discussion pipelines, but are not independent human annotations.
- Exact phrase and citation checks do not prove full semantic entailment; human claim review remains pending.
- Nine answerable and three missing-evidence cases are too small for a production accuracy claim.
- Sources and embeddings were cached; timings measure local inference/orchestration, not live Internet acquisition.
- Local Ollama model switching and host load affect latency. Token counts come from Ollama responses and are not monetary cost.
- The comparison evaluates question answering, not the separate fact/quiz drafting and publication workflow.
