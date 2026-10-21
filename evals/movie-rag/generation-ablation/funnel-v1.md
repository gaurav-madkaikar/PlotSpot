# Fact and quiz generation orchestration ablation

Frozen reviewed exports: **20 movies**

All rows start with the same researcher evidence and writer candidates. The ablation removes or adds downstream critic/readiness stages, so evidence and drafts stay paired.

| Funnel stage | All | Facts | Quiz questions |
|---|---:|---:|---:|
| Writer candidates | 524 | 146 | 378 |
| Critic accepted | 484 | 122 | 362 |
| Full specialist ready | 185 | 68 | 117 |
| Reviewed publication selection | 155 | 54 | 101 |
| Ready but not selected | 30 | 14 | 16 |

| Operational comparison | Result |
|---|---:|
| Critic-only workload reduction | 7.6% |
| Full-pipeline workload reduction | 64.7% |
| Additional reduction after critic | 61.8% |
| Published conversion from all writer candidates | 29.6% |
| Published conversion from ready candidates | 83.8% |
| Published items lost by full specialist pipeline | 0 |

**Observed comparison:** The full specialist pipeline substantially reduced candidate-review workload while retaining every candidate later selected for reviewed publication. The critic alone contributed little reduction; readiness, novelty and corroboration gates did most of the filtering.

## What this does and does not measure

The direct baseline would send every structurally valid writer candidate to manual review. The critic-only arm sends critic accepts. The full specialist arm also applies citation completeness, semantic support, saved-topic novelty, clarity and corroboration/readiness checks.

The reviewed publication set establishes known good retained items. An unselected item may still be valid, so the conversion values above describe the review funnel and are not accuracy or precision claims.

## Limits

- Reviewed publication selection is a high-confidence positive set, not a complete good/bad label for every unselected candidate.
- Published conversion is not semantic precision because valid candidates may be omitted for capacity or topic overlap.
- The arms reuse the same writer candidates; this isolates downstream filtering rather than comparing two independent generations.
- Historical per-call latency and token totals are not comparable across the durable jobs and are excluded.
- Assistant source review is not independent human annotation; a blinded candidate review remains required for semantic quality.
