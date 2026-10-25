# 49. Completing saved content for the ten registered films

Parasite, Spirited Away, The Grand Budapest Hotel and Dune (2021) now each have five filmmaking facts and ten scored story questions. All ten registered discussion films now have complete saved facts/quiz collections. Their metadata is part of the much larger catalog; reviewed content coverage remains ten films.

These additions are assistant-authored, source-reviewed starter banks. They do not come from an Ollama generation run. AI discussion, script-assisted quiz expansion and article fact generation remain separate workflows with their existing checks.

## Why almost no frontend code changed

The movie components already render arrays returned by the API. The content itself lives outside those components:

1. A bank JSON file holds wording, four options, answer index, explanation and evidence markers.
2. A registered Wikipedia adapter retrieves the correct movie/article and returns a section-aware source snapshot with an exact revision.
3. `compile_reviewed_collection` locates the supporting markers in the correct branch: Plot for questions; production, filming, music and related sections for facts.
4. The compiler selects bounded complete-sentence excerpts and constructs stable citation IDs.
5. The explicit preparation command validates the complete collection before publishing it to SQLite.
6. The existing feature endpoint reports that Facts/Quiz are available. The existing React panels then request and display the saved arrays after spoiler consent.

Adding another reviewed movie therefore requires data plus registration, rather than a separate movie-specific React page. The browser test loops over every authored bank and checks loading, scoring, replay and the absence of generation requests.

## Files to follow

- `backend/src/movie_companion/content_banks/496243.json`: Parasite.
- `backend/src/movie_companion/content_banks/129.json`: Spirited Away.
- `backend/src/movie_companion/content_banks/120467.json`: The Grand Budapest Hotel.
- `backend/src/movie_companion/content_banks/438631.json`: Dune (2021).
- `backend/src/movie_companion/reviewed_content.py`: supported IDs, evidence compilation and sentence boundaries. New publications use `reviewed-multi-movie-v2`; existing saved publications retain their previous versions.
- `backend/scripts/prepare_movie_content.py`: explicit prepare/retain/refresh operation.
- `backend/tests/test_reviewed_content.py`: generation-free reads, durable content, wrong-film and missing-branch failures.
- `frontend/e2e/multi-movie-content.spec.ts`: one reusable browser journey for every authored bank.
- `evals/movie-rag/coverage/ten-film-live-publication.json`: exact source/bank hashes, inspected answers, live readiness and preservation checks.

## A citation bug found by inspecting real text

The previous sentence regex interpreted `Dr. Liet Kynes` as two sentences. A Dune citation consequently stopped at `Dr.` even though the original sentence continued.

The compiler now keeps common honorifics and capital initials inside their sentence. Two regression checks exercise the full citation compiler with `Dr. Liet Kynes` and `David J. Peterson`. This is a narrow English heuristic, not a universal sentence parser. The 600-character citation bound remains; an unusually long supporting sentence still fails closed.

This demonstrates why passing tests alone is insufficient: inspect real excerpts as well. A citation can contain the correct answer yet still be awkward or incomplete.

## Sources and publication

| Movie | Revision | New facts | New scored questions |
|---|---|---:|---:|
| Parasite | [1377908085](https://en.wikipedia.org/w/index.php?oldid=1377908085) | 5 | 10 |
| Spirited Away | [1378275530](https://en.wikipedia.org/w/index.php?oldid=1378275530) | 5 | 10 |
| The Grand Budapest Hotel | [1379203663](https://en.wikipedia.org/w/index.php?oldid=1379203663) | 5 | 10 |
| Dune (2021) | [1379707655](https://en.wikipedia.org/w/index.php?oldid=1379707655) | 5 | 10 |

The four source fetches were independent and bounded to two concurrent requests. Each used the fixed HTTPS Wikipedia client with redirects disabled. Full text remains in ignored private snapshots; compact reports record provenance without reproducing whole articles.

Every new claim, selected answer and distractor set was reviewed against the exact excerpt and surrounding source context. Questions use story events and endings; facts use production background. Unconfirmed hidden meanings are not presented as scored truths.

Publication added twenty facts and forty questions. Complete-content hashes verify that the original six collections stayed identical, including generated questions and external reading links. Live GETs confirmed readiness for all ten films, consent protection and equal repeated reads. These saved reads invoke neither Ollama nor a source fetch.

To reproduce a new film's preparation, run from backend:

```sh
.venv/bin/python scripts/prepare_movie_content.py --movie-id 129 --source-snapshot ../.cache/source-snapshots/129.json --report ../evals/movie-rag/coverage/129-publication.json
```

An existing collection is retained by default, so replay changes the report to `retained`. Refresh is explicit and requires another source/content review before replacement.

## Questions and answers

**Are evidence markers RAG?** Not by themselves. They locate known supporting passages for authored content. The independent RAG workflows retrieve evidence for local-model discussion and generation. The starter banks give immediate reviewed content without pretending that authored wording was generated by an agent.

**Does storing a source create its vector index?** No. This operation saves the source snapshot and compiled collections. Evidence vectors are a separate persisted layer used by the RAG workflows.

**Why isn't Generate more enabled for every new movie?** Complete saved content and qualified generation are different capabilities. The movie-specific story verification/generation gate still controls expansion; none of these registrations bypass it.

**What do the new tests prove?** Source identity and branch checks, valid collection shape, durable reads, failure behavior and UI scoring/replay. The synthetic evidence fixtures do not prove the real claims correct. Source review supplies additional evidence, but it is still not an independent held-out accuracy evaluation.

**Do ten complete films mean the whole catalog is covered?** No. Other catalog films retain metadata and truthful unavailable-content states. Broader generated coverage needs additional sources, useful generation inspections and unseen real-film evaluations.

## Validation and next focus

760 backend checks, nine authored-bank browser journeys and the frontend production build passed. The live Spirited Away facts and ten-question quiz were inspected; a correct choice scored 1/10 and did not expose citation details. The original spoiler preference was restored afterward.

The next useful AI milestone is a fresh real-film fact-quality evaluation, followed by broader qualified generation and persistent jobs for slow inference. Expanding authored starter banks alone does not establish model reliability.
