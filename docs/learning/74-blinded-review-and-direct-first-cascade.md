# Blinded review and a direct-first cascade

This slice answers a practical orchestration question: should every PlotSpot discussion request pay for context recovery and a second support-review model, or can the faster direct path handle ordinary questions while specialists recover failures?

## Why the first benchmark was not enough

The first holdout showed 8/12 direct passes and 9/12 specialist passes. That one-case difference was too small to justify nearly three times the median latency. Its exact-phrase labels also came from reviewed project content rather than a new human reviewer.

We therefore separated two concerns:

1. A 24-output human-review packet randomizes the two v1 answers for each question and hides the arm name, automated verdict and reference answer. The reviewer sees the question, answer and up to three retrieved/cited passages. This tests semantic correctness, support, completeness and appropriate abstention without knowing which pipeline produced the response.
2. A new 30-case v2 holdout tests a routing policy. It contains 22 source-backed questions from eleven films absent from v1's answerable set and eight unavailable/private-data controls. Its SHA-256 is `512a6df26f0afc5d2ff31c08b7b08744bbc5216083fe0aee10e1cce70e65e9b4`.

The v2 dataset was frozen before the cascade was implemented or executed. The preregistration then fixed five fallback triggers: a generation/validation error, an invalid response, direct abstention, a missing requested time unit, or an explicitly generic location answer. We did not add triggers after seeing v2 results.

## What the cascade does

The cascade always runs the direct path first. If no trigger fires, it returns that answer. When a trigger fires, it runs the unchanged specialist path and returns the specialist result. This is ordinary Python control flow; no agent framework is required.

For fallback cases, reported latency, calls and tokens include both sequential attempts. This matters because counting only the final specialist call would make the cascade look cheaper than it is.

## Measured result

| Metric | Direct | Always specialist | Direct-first cascade |
|---|---:|---:|---:|
| Automated pass | 26/30 | 27/30 | 27/30 |
| Answerable pass | 18/22 | 19/22 | 19/22 |
| Missing/private-data controls | 8/8 | 8/8 | 8/8 |
| Median latency | 3.447 s | 10.221 s | 4.785 s |
| P95 latency | 5.962 s | 15.164 s | 7.418 s |
| Chat calls | 30 | 50 | 41 |
| Embedding calls | 30 | 30 | 40 |

The cascade fired ten times: nine direct abstentions and one generation/validation error. It recovered the Inception reward question while retaining the direct answer that the specialist lost for Grand Budapest Hotel. It matched always-specialist quality with nine fewer chat calls and roughly half the median latency.

The result also reveals an evaluation limitation. Direct answered “Thomas Anderson” and “linguist” correctly in two cases, but the exact labelled citation was not selected, so the automated grader failed them. Human review may judge the answer text differently from the citation-recall gate. This is exactly why automated retrieval checks and human answer assessment should remain separate metrics.

## Why it is not live yet

The preregistered adoption rule passed, but this is still a small local benchmark. The direct fallback sends every abstention, including valid missing-data refusals, through the specialist path. That preserves safety here but spends extra work on all eight controls. The result uses reviewed project labels and local timing, not external human annotations or production concurrency.

We will keep the live Discuss routing unchanged until the blinded review is complete and a larger external set confirms the result. The consumed v2 holdout must not be used to tune new triggers.

## Files to inspect

- `backend/src/movie_companion/blind_human_review.py`: creates the blinded packet and scores completed labels.
- `backend/src/movie_companion/cascade_benchmark.py`: contains the frozen fallback rules and composition math.
- `evals/movie-rag/orchestration-benchmark/cascade-preregistration-v1.json`: records the policy before execution.
- `evals/movie-rag/orchestration-benchmark/cascade-comparison-v1.md`: contains paired case outcomes.

The main lesson is that multiple agents should earn their cost on measured failure modes. A direct-first policy can preserve specialist recovery without charging every successful request for another model, but only if the fallback rule is frozen, costs include retries, abstention behavior is tested, and humans inspect semantic quality.
