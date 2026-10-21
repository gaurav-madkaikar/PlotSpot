# 57. Extending movie content and checking real RAG behavior

This note records the original publication and inspection. [Lesson 58](58-discussion-retrieval.md) covers the subsequent retrieval/citation changes and wider baseline comparison; the original labels and failed grades below remain intact.

The Dark Knight (TMDB 155) now has five production facts, ten scored story questions and a registered source for local AI discussion. Shared saved content covers eleven films. Browse `/movies/155`, allow spoilers and use the existing Facts, Quiz and Discuss sections.

## Two different paths

**Saved content:** inspected bank JSON → exact source evidence → citation compiler → publication checks → SQLite → GET endpoint → existing React panels.

**AI discussion:** question → registered article → section-aware chunks → local Ollama embeddings → persistent Chroma vectors → question embedding → scoped top-three retrieval → local chat model → response/citation validation → UI.

The new starter bank is assistant-authored and inspected against a real article revision. It is not an Ollama-generated bank. Discussion uses the actual local models. Saved facts and quizzes require neither inference nor a source fetch when opened or replayed.

## What changed

- `wikipedia_source.py` maps movie 155 to The Dark Knight. A browser/model cannot provide a different URL.
- `content_banks/155.json` stores concise wording, four choices, answer indexes, explanations and evidence markers.
- `reviewed_content.py` includes the bank in explicit preparation. The same compiler requires plot evidence for questions and production-related evidence for facts.
- Existing feature inventory and UI panels automatically expose a published bank. No movie-specific frontend page was needed.
- `evaluate_registered_movie_rag.py` supports inspecting another registered film with frozen source-specific labels. This leaves the earlier Interstellar learning benchmark unchanged.

The [inspected article revision](https://en.wikipedia.org/w/index.php?oldid=1378704545) contains 76,482 extracted characters and 167 section-aware chunks at 600 characters with 100-character overlap. Source snapshots and vectors remain ignored local artifacts; compact reports record provenance.

Every fact, selected answer, explanation and set of distractors was inspected against the supporting passage and surrounding context. Subjective interpretations are not presented as uniquely correct scored answers. The original ten complete collections were hashed before publication and remained unchanged afterward, including existing additional questions and reading links.

## What happened with actual Ollama

The development cases were labelled before running `nomic-embed-text:v1.5` and `llama3.2:3b` through `answer_movie_question`, the same function used by ordinary Wikipedia discussion. They are a five-case development inspection, not an independent holdout.

| Question | Observed behavior | Automated result |
|---|---|---|
| Who composed the music? | Named James Newton Howard and Hans Zimmer | Pass |
| What cover title was used in Chicago? | Named Rory’s First Kiss | Pass |
| Why does Dent claim he is Batman? | Abstained; top-three hits missed the plot statement | Fail |
| Why does Batman take blame at the ending? | Answered with the idea of preserving hope; cited thematic analysis rather than the labelled plot passage | Fail against original labels |
| What did I write in my private diary? | Correctly abstained | Pass |

The ending result illustrates a label limitation: a cited analysis passage supports the main motivation but was absent from the pre-run supporting-ID set. Another cited passage was unnecessary. The report records assistant source inspection separately and preserves the original labels and 3/5 automated grade. Changing the expected IDs after seeing the output would conceal the original evaluation result.

The decoy case illustrates a genuine retrieval problem. The correct plot statement exists, but broad semantic retrieval ranked themes and writing passages above it. Their cosine scores were high, yet they did not answer the event question. The model correctly declined to invent the missing answer. Better event routing or retrieval can address this; rewriting the saved bank cannot.

A separate request through the actual HTTP endpoint also returned both composers with movie-scoped citations. This verifies the source/embedding/API path for one question; it does not replace the five-case report or establish general accuracy.

## Reproduce and read the evidence

From backend:

```sh
.venv/bin/python scripts/prepare_movie_content.py --movie-id 155 --source-snapshot ../.cache/source-snapshots/155.json --report ../evals/movie-rag/coverage/155-publication.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/dark-knight-discussion-cases.json --output ../evals/movie-rag/coverage/dark-knight-discussion-rerun.json
```

Preparation retains an existing collection by default. Refresh explicitly replaces it and requires another source/content review. For the original labels, use the exact frozen snapshot; changes to source content or chunk settings fail before model calls. The inspection script returns exit status 1 when a case fails and still saves its report.

Reports are in `evals/movie-rag/coverage/`: publication, source/bank hashes and preservation, pre-run cases, actual model outputs and the live API inspection. Read the outputs and citations as well as the aggregate score.

## Questions and answers

**Why can the same UI show a new film without new React code?** Components render arrays from generic movie-scoped endpoints. Registration and publication change the data and feature inventory, not the page structure.

**Does a ready bank mean its AI generation is qualified?** No. This film has inspected saved content and Wikipedia discussion. No screenplay or publisher-news source was added, and Generate more remains unavailable. Its draft/preparation gates were not relaxed.

**Is a high similarity score evidence that an answer is correct?** No. Similarity measures how related a passage is to the question. A paragraph about Dent’s symbolism can be highly related while omitting why he makes a particular claim.

**Why does the evaluator use expected phrases and passage IDs?** They make reproducible checks possible without demanding one fixed generated sentence. They still need complete, inspected labels and separate claim-support review. They are not an entailment oracle.

**Can we claim 60% production accuracy?** No. Three of five automated development checks passed, one label set was incomplete, and these cases are now consumed development data. A production claim needs broader independent labels and a clearly defined metric.

**What do the automated tests prove?** Contract and publication validity, correct evidence branches, movie isolation, durable generation-free reads, consent, frozen-label rejection, scoring and UI recovery. Assistant source inspection provides a different kind of evidence; neither proves automatic publication safe across the full catalog.

## Validation and next focus

928 backend checks, sixteen content/discussion browser journeys and the frontend production build passed. Live feature inventory reports all eleven collections ready. The Dark Knight’s five facts and ten questions repeat equally and require spoiler consent; live scoring reached 1/10 with no evidence disclosure on a correct answer. All ten previous collections remain unchanged.

Next: improve event retrieval and citation selection with reviewed development labels, then measure against fresh independent cases before widening automated preparation. Parallel research comparison, accounts and community remain pending original milestones.
