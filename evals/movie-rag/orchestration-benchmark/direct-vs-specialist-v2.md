# Direct versus specialist movie RAG

Run: 2026-10-17T07:48:14.373937+00:00

Both arms used the same frozen source snapshots, labels, retriever, embedding model and answer model. The specialist arm additionally used context recovery and a separate support-review model.

| Metric | Direct single agent | Specialist pipeline |
|---|---:|---:|
| Automated pass | 26/30 (86.7%) | 27/30 (90.0%) |
| Answerable cases | 18/22 | 19/22 |
| Missing-evidence controls | 8/8 | 8/8 |
| Supporting hit at 3 | 20/22 | 20/22 |
| Median latency | 3.447 s | 10.221 s |
| P95 latency | 5.962 s | 15.164 s |
| Chat calls | 30 | 50 |
| Prompt / output tokens | 46717 / 1968 | 55395 / 4334 |

**Observed comparison:** The specialist pipeline improved automated holdout quality, with additional latency and model calls.

## Per-case outcome

| Case | Expected | Direct | Specialist | Direct latency | Specialist latency |
|---|---|---|---|---:|---:|
| spirited-away-parents-transformed | answered | pass | pass | 4.794 s | 12.961 s |
| spirited-away-boiler-worker | answered | pass | pass | 3.292 s | 10.168 s |
| the-dark-knight-last-bank-robber | answered | fail | fail | 2.796 s | 2.97 s |
| the-dark-knight-bruces-exit-plan | answered | pass | pass | 4.798 s | 15.164 s |
| the-matrix-neo-name | answered | fail | pass | 3.88 s | 12.473 s |
| the-matrix-pill-choice | answered | pass | pass | 5.962 s | 11.705 s |
| inception-fischer-plan | answered | pass | pass | 3.952 s | 11.412 s |
| inception-cobb-reward | answered | fail | pass | 1.48 s | 9.043 s |
| the-truman-show-seahaven-secret | answered | pass | pass | 4.154 s | 12.627 s |
| the-truman-show-world-controller | answered | pass | pass | 3.272 s | 10.275 s |
| the-grand-budapest-hotel-zero-first-job | answered | pass | fail | 4.013 s | 2.763 s |
| the-grand-budapest-hotel-famous-bequest | answered | pass | pass | 7.418 s | 11.764 s |
| interstellar-dust-coordinates | answered | pass | pass | 4.64 s | 14.381 s |
| interstellar-mann-motive | answered | pass | pass | 3.418 s | 11.374 s |
| arrival-louise-profession | answered | fail | fail | 3.1 s | 10.285 s |
| arrival-ship-count | answered | pass | pass | 2.968 s | 9.477 s |
| dune-new-fief | answered | pass | pass | 4.569 s | 16.191 s |
| dune-spice-purpose | answered | pass | pass | 2.272 s | 8.625 s |
| parasite-scholars-gift | answered | pass | pass | 4.003 s | 11.912 s |
| parasite-first-position | answered | pass | pass | 5.385 s | 12.767 s |
| knives-out-marta-role | answered | pass | pass | 5.297 s | 14.621 s |
| knives-out-lie-reaction | answered | pass | pass | 3.212 s | 10.05 s |
| private-voice-actor-phone | insufficient_evidence | pass | pass | 2.744 s | 2.033 s |
| unpublished-director-notes | insufficient_evidence | pass | pass | 2.411 s | 3.247 s |
| private-bank-account | insufficient_evidence | pass | pass | 3.476 s | 3.14 s |
| viewer-watch-history | insufficient_evidence | pass | pass | 2.864 s | 2.942 s |
| private-actor-email | insufficient_evidence | pass | pass | 2.712 s | 2.301 s |
| studio-payroll-record | insufficient_evidence | pass | pass | 3.093 s | 3.634 s |
| unreleased-sequel-ending | insufficient_evidence | pass | pass | 3.069 s | 3.341 s |
| private-medical-record | insufficient_evidence | pass | pass | 3.563 s | 3.719 s |

## Limits

- Labels are frozen and independent of the compared discussion pipelines, but are not independent human annotations.
- Exact phrase and citation checks do not prove full semantic entailment; human claim review remains pending.
- 22 answerable and 8 missing-evidence cases are too small for a production accuracy claim.
- Sources and embeddings were cached; timings measure local inference/orchestration, not live Internet acquisition.
- Local Ollama model switching and host load affect latency. Token counts come from Ollama responses and are not monetary cost.
- The comparison evaluates question answering, not the separate fact/quiz drafting and publication workflow.
