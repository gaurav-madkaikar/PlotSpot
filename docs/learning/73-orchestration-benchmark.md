# 73 — Direct versus specialist orchestration benchmark

This benchmark asks whether PlotSpot’s additional context and support-review stages improve movie question answering enough to justify their cost. It compares two read-only pipelines and never writes published content.

## Compared systems

The **direct** arm embeds the question, runs the current hybrid word/vector retriever, and makes one grounded `llama3.2:3b` answer call. Exact source quotes and citation membership remain code-validated.

The **specialist** arm uses the same embedding model, answer model, retriever, source snapshots and top-three anchors. It additionally recovers complete/adjacent source context and asks `qwen3.5:9b` to review whether the proposed answer is supported. Unsupported or uncertain answers become abstentions.

Both arms run sequentially. Case order alternates direct-first and specialist-first to reduce systematic warm-model bias. Ollama reports prompt tokens, output tokens and inference durations; these are local resource measurements, not API costs.

## Frozen holdout

`holdout-v1.json` was frozen at SHA-256 `9b40e967bd614675c7c9a92c5d27f9b134965168dcc9129b4b50829b2dfa06f6` before either arm ran. It contains nine objective answer cases from the nine newly published films and three missing/private-data controls. Positive labels use already reviewed published quiz answers and exact immutable Wikipedia source spans. This makes the labels independent of the compared discussion pipelines, but they are not independent human annotations.

Every run rechecks source file hashes, revisions, chunk policy, snapshot keys and exact excerpt-to-passage mappings before model I/O. The first run is immutable at SHA-256 `8f78ace6622ec2293284700cf228c777a34fe5203770ce4be88af3ae4aaab0bd`.

## Results

| Metric | Direct | Specialist |
|---|---:|---:|
| Automated pass | 8/12 (66.7%) | 9/12 (75.0%) |
| Answerable cases | 5/9 | 6/9 |
| Missing/private-data controls | 3/3 | 3/3 |
| Labelled supporting hit at 3 | 8/9 | 8/9 |
| Median latency | 3.540s | 9.642s |
| P95 latency | 5.867s | 14.177s |
| Chat calls | 12 | 19 |
| Prompt tokens | 19,247 | 24,222 |
| Output tokens | 801 | 1,523 |

The specialist arm gained 8.3 percentage points and one net passing case. It used 58.3% more chat calls, 25.8% more prompt tokens, 90.1% more output tokens, 28.4% more combined prompt/output tokens, and 2.72 times the median latency.

The direct 95% Wilson interval is 39.1–86.2%; the specialist interval is 46.8–91.1%. They overlap widely. Seven cases passed in both arms, two passed only with specialists, one passed only in the direct arm, and two failed in both. With only three discordant pairs, the observed difference is not evidence that specialists are generally superior.

## What the failures teach

- **Shawshank:** direct generation failed validation after retrieval missed labelled support; context recovery produced the complete weekly-letters answer and passed review.
- **Forrest Gump:** direct output said only “three,” omitting the requested unit. The specialist returned “3 years.”
- **The Prestige:** the direct arm returned the correct city, while the specialist path ended in a validation error. Extra stages can introduce failure.
- **The Godfather:** the direct answer said “another country” instead of Sicily; the specialist safely abstained. Neither met the labelled answer.
- **The Lion King:** both arms answered the broader “Pride Lands of Eastern Africa” instead of Pride Rock. The specialist reviewer marked that answer supported, exposing a relation-specific false positive.

## Decision

The current evidence does not justify running the specialist pipeline for every question. Direct RAG is substantially faster and passed most successful specialist cases. Context recovery and review did repair two failures, but added one failure and did not catch the Lion King relation error.

A promising next design is a measured cascade: run direct RAG first, then invoke the specialist path only after a response-validation error or a deterministic completeness warning such as a missing unit. That idea is post-hoc and has not been benchmarked; it must receive a new preregistered evaluation rather than being scored against this consumed holdout.

## Reproduce the run

With the frozen `.cache/expanded20/sources` snapshots and reviewed Ollama model digests available:

```sh
backend/.venv/bin/python backend/scripts/benchmark_agent_orchestration.py \
  --output evals/movie-rag/orchestration-benchmark/run-v2.json \
  --markdown evals/movie-rag/orchestration-benchmark/comparison-v2.md
```

Use new output names. The original `run-v1.json` and `comparison-v1.md` are evidence and must not be overwritten.

## Limits

Phrase/citation checks do not prove full entailment. The set is small, uses cached Wikipedia sources, and measures question answering rather than fact/quiz drafting. Timings include local model switching and exclude Internet acquisition. Independent human review and a larger preregistered benchmark are required before resume claims about semantic accuracy or cost reduction.
