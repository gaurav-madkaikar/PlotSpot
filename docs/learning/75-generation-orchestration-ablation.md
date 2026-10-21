# What the generation agents actually add

PlotSpot's content workflow has several stages: researchers collect movie-scoped evidence, a writer creates fact or quiz candidates, a critic assesses those candidates, deterministic readiness gates check citation support and novelty, and a reviewer explicitly selects items for publication.

This ablation asks which downstream stages reduce work without losing candidates that eventually became reviewed shared content.

## The three compared paths

The comparison reuses the same 524 writer candidates from the twenty-film publication workflow. That keeps research evidence and writer output identical.

1. **Direct writer:** every structurally valid writer candidate goes to manual review.
2. **Writer plus critic:** only candidates with an `accept` verdict go to manual review.
3. **Full specialist pipeline:** critic accepts must also pass citation completeness, semantic-support, saved-topic novelty, clarity, corroboration and readiness checks.

This is an ablation rather than three new generations. Reusing candidates isolates the value of downstream filtering and avoids confusing writer randomness with critic performance.

## Results

| Stage | All | Facts | Quiz questions |
|---|---:|---:|---:|
| Writer candidates | 524 | 146 | 378 |
| Critic accepted | 484 | 122 | 362 |
| Full specialist ready | 185 | 68 | 117 |
| Reviewed publication selection | 155 | 54 | 101 |

The critic alone reduced review work by only **7.6%**. It accepted 92.4% of writer candidates. The complete specialist pipeline reduced review work by **64.7%** and retained all 155 candidates later chosen for publication.

The effect differs by content type. Full readiness reduced fact candidates by 53.4% and quiz candidates by 69.0%. Quiz novelty and corroboration checks therefore account for much of the useful filtering. The critic cannot replace those code-owned rules.

Of the 185 ready candidates, 155 were selected and 30 were not. That is an 83.8% publication conversion, compared with 29.6% from the raw writer pool. These figures describe the review funnel. They are not accuracy or precision because reviewers can omit valid candidates due to bank capacity or topic overlap.

## Why the critic should not be its own evaluator

It would be circular to call the critic accurate because its accepted candidates passed the critic. This report uses only observable stage transitions and the later reviewed publication selection. It treats published items as known positives and makes no negative claim about unselected items.

Semantic quality still needs independent labels. A blinded reviewer should inspect support, content eligibility, option quality and novelty without seeing whether the critic accepted the candidate. That future review can estimate acceptance precision and useful-candidate recall.

## What this teaches about multi-agent design

Adding an agent is useful only when its distinct responsibility changes a measured outcome. Here, the critic contributes some rejection and uncertainty decisions, but the largest reduction comes from deterministic and retrieval-backed gates after it. The production lesson is to combine narrow model judgement with code-owned invariants rather than asking another model to approve everything.

Inspect `backend/src/movie_companion/generation_ablation.py` for the funnel validation and `evals/movie-rag/generation-ablation/funnel-v1.md` for the generated comparison. The audit cannot publish content or call a model.
