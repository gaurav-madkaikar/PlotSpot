# 35. Reusable content across movies

Inception, Arrival and The Matrix now each have five background facts and ten scored story questions, alongside the existing Interstellar collection. They use explicitly reviewed Wikipedia mappings and saved source revisions. This slice expands the curated baseline; it does not add an autonomous researcher or claim that AI generated these questions.

## The flow

```text
Reviewed movie ID and authored bank
              +
Section-aware Wikipedia revision
              ↓
Compiler finds supporting sentences
              ↓
Validate complete quiz and facts
              ↓
Publish one SQLite collection atomically
              ↓
Feature inventory → UI loads saved content
```

`content_banks/{movie_id}.json` contains the question, four choices, correct answer, explanation and evidence markers. Facts have their own titles, text and markers. `reviewed_content.py` binds these entries to a specific article revision: quiz evidence must come from Plot; background evidence comes from production, filming, casting, effects or music sections. It selects complete supporting sentences within the existing 600-character citation limit. Missing evidence blocks the entire publication.

Wording and distractor correctness were reviewed against the real source excerpts. Marker membership is only a deterministic evidence-location check: it does not prove a claim, judge whether distractors are ambiguous, or establish whether a fact is interesting. We deliberately avoid scoring an interpretation of Inception's final top as a confirmed answer.

## Preparation versus serving

Prepare an explicitly supported film from the project root:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/prepare_movie_content.py \
  --movie-id 27205 --report .cache/preparation/inception.json
```

The command reports source reading, validation and publication. An existing collection is retained without network/model calls. Add `--refresh` to deliberately re-read and replace it; an older version is not silently overwritten. `--source-snapshot path.json` supports reproducible preparation from a previously fetched revision, and rejects a different movie's snapshot. Interstellar remains the default when no movie ID is supplied.

The Facts and Quiz UI use GET requests. These reads do not fetch Wikipedia, embed text or call Ollama. The feature inventory discovers which movie collections are actually published, so no new frontend movie-ID list is needed. The whole collection stays behind spoiler consent because sources have unknown spoiler classification.

The three new quizzes report that more questions are unavailable. Their initial bank does not yet contain unused generation targets. Interstellar's existing local-model expansion remains available when supported unused targets exist.

## Questions and answers

**Why save the source revision?** Wikipedia changes. A revision URL makes each citation refer to the evidence used during preparation, rather than whatever the article says today.

**What if a source changes or a refresh fails?** If a marker is absent or appears in the wrong section, preparation fails before publishing. The old complete collection remains usable. A successful refresh also checks that the original publication has not changed concurrently.

**Why publish facts and quiz together?** A user should receive a complete prepared collection. SQLite publishes the validated payload in one transaction; it does not expose a half-written quiz while facts are still being assembled.

**Where is RAG here?** This compiler uses deterministic evidence selection for authored entries. It does not need vector retrieval or a model. Discuss still uses the learner's RAG pipeline, and Interstellar's extra-question flow still calls Ollama. The next content-generation slice can retrieve scoped evidence and ask a local model to propose content, then compare those proposals with this baseline.

**Does this scale automatically to all 1,500 movies?** No. Only four movies have reviewed saved-content banks. Discovery and metadata cover a much larger catalog. General preparation needs reviewed source discovery, generated proposals, quality gates and measured coverage rather than invented content to meet a quota.

**Are the tests an AI quality evaluation?** No. Backend tests exercise routing, provenance, publication and reads; browser tests exercise interaction. The live-source review establishes support for these particular authored entries. Future model evaluations must separately measure support, ambiguity, duplicates, abstention, spoiler leakage and failures on labelled development and held-out cases.

## Verification

- 458 backend checks passed, including fourteen new multi-movie contract cases.
- Production build and ten focused browser journeys passed.
- Three real source revisions published thirty scored questions and fifteen facts; publication reports are in `evals/movie-rag/prepared-*.json`.
- Live Inception displayed five facts, ten questions and correct scoring. Unknown or unprepared films still show honest coverage messages.

Sources: [Inception](https://en.wikipedia.org/w/index.php?oldid=1379453144), [Arrival](https://en.wikipedia.org/w/index.php?oldid=1377517038), [The Matrix](https://en.wikipedia.org/w/index.php?oldid=1379344781). Wikipedia excerpts retain source attribution in the UI; the banks use concise authored wording. These are production-background collections, not a live news feed.
