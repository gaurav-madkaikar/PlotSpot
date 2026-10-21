# Discovery evaluation

The app uses `catalog_search.search_catalog`, not the legacy vector-only route. The broad suite runs the actual service with saved TMDB metadata and local Ollama embeddings, without network requests to TMDB.

## Preserved baseline (200 movies)

43 labelled development cases: 18 plot descriptions, 5 themes, 5 moods, 6 genre/filter combinations, 4 identity/typo searches, and 5 expected-empty cases. Labels were saved before execution. Existing known regressions are included. The snapshot fingerprint prevents accidental comparison against a different collection.

| Metric | App search | Raw embedding baseline |
| --- | ---: | ---: |
| Expected film in top 5 | 26/38 (68.4%) | 25/38 (65.8%) |
| Expected film in top 20 | 27/38 (71.1%) | 33/38 (86.8%) |
| Mean labelled-target recall at 20 | 69.3% | 83.3% |
| Mean reciprocal rank at 20 | 0.567 | 0.540 |
| Correct empty results | 5/5 | 1/5 |
| Returned films violating labelled constraints | 0 | 35 |
| Execution errors | 0 | 0 |

Top-5 hits by group: plot 13/18, theme 1/5, mood 2/5, constraint 6/6, identity 4/4. These groups are small and deliberately varied; the percentages are not population estimates.

## Findings

All eleven app top-20 misses excluded a labelled target at the candidate gate; eight were recovered by raw embedding ranking. For example, `first contact where language matters more than fighting` misses Arrival, and `reality is artificial and controlled by machines` misses The Matrix. `something dreamlike and magical` misses Spirited Away. `stories about masked crime fighters` returns no results despite Batman and Spider-Man in the catalog.

Some constraints are overinterpreted: `a quirky charming hotel adventure` triggers the Adventure genre requirement, excluding The Grand Budapest Hotel, whose metadata is Comedy/Drama. Conversely, shared generic synopsis words can admit unrelated films.

The baseline applies explicit UI filters but omits query-derived genre/theme constraints and abstention. It establishes whether a relevant stored embedding can rank near the top; it is not a proposed production replacement. Its 35 violations count films that fail explicit or manually labelled genre expectations, not 35 failed queries.

## Limits

Relevant IDs are illustrative targets, not exhaustive judgments. A hit means at least one labelled film appeared; it does not prove that every other returned film was relevant. Precision and overall accuracy are therefore not claimed. Mood/theme labels use human story interpretation. Development data is not held-out validation. Baseline latency can reuse cached query embeddings and should not be used as a fair speed comparison.

## Reproduce

From the project root, with Ollama running and `nomic-embed-text:v1.5` installed:

```sh
backend/.venv/bin/python backend/scripts/evaluate_broad_search.py
```

Labels: `broad-cases.json`. Detailed outputs, top-five titles, expected IDs, gate diagnostics, per-group metrics, and snapshot/model metadata: `broad-ollama-report.json`. Earlier ten-case development reports are retained for history.

## Implemented hybrid experiment

The live application now combines 24 vector candidates with 8 BM25 candidates and grades the deduplicated metadata using local `qwen3.5:9b`. Reviewed model digests, bounded structured ratings, strict explicit filters, sanitized failures, shared in-process workload limits and snapshot-aware ranked caches are implemented. Metadata preparation supports 1,500 movies with provider keywords/alternative titles and resumable atomic publication.

The final version is `hybrid-ollama-v4`. The preserved 200-film snapshot allows a same-corpus comparison:

| Metric | Previous app | Final hybrid v4 |
| --- | ---: | ---: |
| Expected film in top 1 | see original report | 25/38 |
| Expected film in top 5 | 26/38 | 31/38 |
| Expected film in top 20 | 27/38 | 33/38 |
| Mean labelled-target recall at 20 | 69.3% | 82.3% |
| MRR at 20 | 0.567 | 0.730 |
| Correct empty | 5/5 | 5/5 |
| Labelled filter violations | 0 | 0 |
| Execution errors | 0 | 0 |

The smaller Llama relevance checker returned expected targets in the top five for 23/38 queries. Qwen v3 reached 32/38 top-five and 32/38 top-twenty; v4 trades one top-five hit for better top-twenty coverage (33/38). Reports retain these experiments rather than hiding regressions. Five final top-twenty misses remain.

Final v4 development p95 was 31.6 seconds on this machine, with catalog embedding preparation overlapping part of the run. Earlier Qwen v3 p95 was 22.5 seconds. These are observed local timings, not an isolated performance benchmark. Latency remains a material limitation; cached repeated requests/pagination avoid new model inference.

`relevance-calibration.json` replays final development ratings at grades 1, 2 and 3. Labelled hit/empty metrics tie; incomplete labels cannot establish an optimal threshold or precision. We retain the predeclared grade-2 clearly-relevant rule. No validation labels were used to tune this rule.

## Expanded-catalog validation

The 24 queries in `validation-cases.json` were authored and frozen before execution: 20 positive paraphrase/theme/mood queries and four expected-empty or malicious requests. `validation-1500-cases.json` changes only the catalog fingerprint, after verifying all expected IDs are present. Film targets overlap development: this tests new queries, not a wholly independent film domain. Relevant labels are still illustrative, not exhaustive.

The expanded snapshot has 1,500 unique TMDB IDs, 768-dimensional embeddings, keywords for 1,421 films and alternative titles for 1,449. All 75 live browse pages were checked for page size and duplicate IDs. This establishes ingestion/pagination integrity separately from semantic quality.

Reproduce without exposing credentials:

```sh
backend/.venv/bin/python backend/scripts/evaluate_broad_search.py --hybrid --path .cache/eval-snapshots/catalog-200.json --output evals/discovery/hybrid-development.json
backend/.venv/bin/python backend/scripts/evaluate_broad_search.py --hybrid --cases evals/discovery/validation-1500-cases.json --output evals/discovery/hybrid-1500-validation.json
```

Local Ollama must have the reviewed `nomic-embed-text:v1.5` and `qwen3.5:9b` artifacts. Query data remains local. The grader has no tools; injection abstention measurements do not prove general prompt-injection immunity. Single-process caches/locks do not coordinate multiple deployments. The semantic candidate pool is capped at 32, so the shortlist is not exhaustive catalog search.

Final 200-film misses include artificial reality controlled by machines (The Matrix), stealing secrets from dreams (Inception), a secretly filmed everyday life (The Truman Show), class divisions (Parasite), and surveillance/privacy (The Truman Show). These remain recorded failures, not removed labels. The expanded catalog is assessed separately and its numbers must not be presented as a same-corpus improvement over the 200-film baseline.

Live HTTP/browser verification: `hero movies` returns Spider-Man: No Way Home, The Dark Knight, Iron Man and Justice League, alongside incorrect recommendations including Paths of Glory, Fury and The Quintessential Quintuplets Movie. See `live-1500-smoke.json`. Two cached requests took 0.321 and 0.305 seconds; the uncached live search took 30.8 seconds. These observations demonstrate cache reuse and remaining precision problems, not production performance guarantees. Default Uvicorn access logs now remove query strings; structured discovery logs retain only a query hash.

## Frozen-query validation results

Final v4 completed all 24 expanded-catalog cases with zero execution errors:

| Metric | Hybrid app | Raw vector baseline |
| --- | ---: | ---: |
| Expected film in top 1 | 5/20 | 4/20 |
| Expected film in top 5 | 15/20 | 10/20 |
| Expected film in top 20 | 17/20 | 18/20 |
| Correct empty | 4/4 | 0/4 |
| Mean labelled-target recall at 20 | 81.7% | 86.7% |
| MRR at 20 | 0.465 | 0.344 |

The hybrid approach improves top-five ranking and abstention but loses one top-twenty target relative to raw vectors. Misses: rescuing transformed parents (Spirited Away), revenge after fifteen years of captivity (Oldboy), and gentle magical stories with a courageous young heroine (Spirited Away). These are not removed or relabelled after execution. No prompt/threshold was changed using these results.

Observed uncached app p95 was 44.4 seconds; one live browser model request overlapped this run. Baseline timing reuses app query embeddings and is not a fair speed comparison. The corpus and queries differ from the development benchmark; do not claim a direct percentage improvement across those two datasets. Four empty/adversarial cases are a small observation, not proof of general attack resistance. See `hybrid-1500-validation.json` for complete candidates, ratings, results and model/configuration metadata.
