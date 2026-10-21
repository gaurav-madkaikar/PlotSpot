# 72 — Reviewed twenty-film publication

PlotSpot now has twenty shared movie banks produced by the durable multi-source research workflow and admitted through explicit review. Viewing a movie does not run research or call Ollama. The application reads the reviewed version from SQLite, while generation remains a separate internal workflow.

## What was published

The set contains Inception, Interstellar, Arrival, The Matrix, Knives Out, Parasite, Spirited Away, The Truman Show, The Grand Budapest Hotel, Dune (2021), The Dark Knight, The Shawshank Redemption, The Godfather, Pulp Fiction, Fight Club, Forrest Gump, The Prestige, WALL-E, The Lion King and Mad Max: Fury Road.

Each bank satisfies the publication policy:

- at least five production/background facts;
- at least ten scored story questions;
- citations on every item;
- at least two publisher families represented in facts;
- at least two publisher families represented in the scored quiz;
- a review selection pinned to the job, report and bank hashes;
- an atomic publication receipt stored with the content write.

The final stored corpus contains 113 facts and 215 quiz items. Of the quiz items, 214 are scored questions and one is an interpretation prompt. There are 332 citations across 25 normalized publisher families.

## Reproducing the integrity audit

From the repository root:

```sh
backend/.venv/bin/python backend/scripts/audit_published_movie_content.py
```

The command reads the immutable review audit, publication receipts and current content database. It recomputes each stored payload hash, matches the job/report/version/timestamp identities, loads the collection through the same validated store used by the API, and recalculates content and publisher coverage. A mismatch stops the command without creating a passing report.

Outputs:

- `evals/movie-rag/expanded-20/published-content-audit.json` for automated inspection;
- `evals/movie-rag/expanded-20/published-content-audit.md` for reviewers;
- `evals/movie-rag/expanded-20/final-review-audit.json` for the pre-publication evidence;
- `evals/movie-rag/expanded-20/publication-receipts.json` for committed writes.

## What the audit proves

It proves that the twenty expected reviewed selections reached the shared database without later payload drift, that the API can load structurally valid banks, and that every bank meets the configured content and publisher-diversity minimums. It also makes the current portfolio numbers reproducible instead of copying hand-counted totals into a README.

It does not prove that every fact is true, every distractor is ideal, or two publishers are independent. Assistant source review is not a substitute for independent human labels. The report also excludes live-search reliability, local-model latency, resource usage and concurrent-user capacity.

## Code to follow

1. `published_content_audit.audit_published_content` performs the fail-closed checks and computes metrics.
2. `published_content_audit.render_markdown` turns the same result into a reviewer-friendly report, avoiding a second source of metric logic.
3. `audit_published_movie_content.py` is a thin command-line boundary with bounded inputs and atomic output replacement.
4. `test_published_content_audit.py` checks the passing path and rejects altered audit, report and payload identities as well as incomplete receipt sets.

## Next evaluation work

The next quality benchmark needs fresh labels that were not used during prompt or policy development. It should sample published facts and questions across film eras and source types, ask independent human reviewers to label support and ambiguity, preserve disagreements, and report confidence intervals. A first small direct-versus-specialist QA run using frozen evidence is now recorded in [Lesson 73](73-orchestration-benchmark.md); larger independent human labels and a fact/quiz drafting comparison are still required before making production-quality or cost claims on a resume.
