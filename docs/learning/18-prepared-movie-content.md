# Prepare once, serve many times

## What you can see now

Open Interstellar, enable spoilers, then open Quiz or News & facts. Content loads automatically: ten scored story questions, one unscored interpretation, and five production facts. Replay resets only your choices. Refreshing the page or restarting the backend retains the same content.

The current collection is a curated starter bank compiled against a previously fetched real Wikipedia revision. The preparation step validates supporting source statements; it does not ask an LLM to invent new questions. Discuss still runs your local-Ollama embedding, retrieval and answer code. Autonomous content discovery/generation and coverage of other movies remain future work.

## The two paths

```text
Preparation (explicit local command)
  reviewed bank + real source snapshot
  → verify statements and attach revision citations
  → check uniqueness and minimum counts
  → atomically publish quiz + facts to SQLite

Viewing (no generation)
  open tab + spoiler permission
  → GET saved quiz/facts
  → SQLite read + response validation
  → Zod validation → display / local quiz score
```

`prepared_content.py` defines the expanded collection and compiler. `content_store.py` owns persistence and publication rules. `main.py` serves saved collections. A future preparation agent can output validated `MovieQuiz`/`MovieFacts` objects and use the same publisher; this keeps model behavior separate from storage and viewer latency.

## Why this differs from the earlier caches

- The TMDB dictionary avoids repeated metadata requests for a short time and disappears when the process restarts.
- React Query caches browsing responses in the browser session.
- Chroma persists source passage embeddings for RAG. It stores evidence vectors, not finished quizzes.
- SQLite now persists the finished collection: wording, answer choices, answer keys, explanations, citations, preparation time and content version.

This is a saved publication, not a cache with a short automatic expiry. Readers continue seeing the existing collection until an explicit preparation refresh succeeds. Source changes do not silently replace content on a page visit.

## Preparation commands

From the backend directory:

```sh
.venv/bin/python scripts/prepare_movie_content.py
```

If the current content version is already saved, this returns immediately without source/model calls. First preparation fetches Wikipedia. To use an existing real-source snapshot:

```sh
.venv/bin/python scripts/prepare_movie_content.py --source-snapshot ../data/private/movie-rag/source.json
```

To explicitly recheck the latest source and publish a replacement:

```sh
.venv/bin/python scripts/prepare_movie_content.py --refresh
```

A failed source fetch, missing supporting statement, duplicate question/fact, missing citation, or incomplete collection prevents publication. SQLite stores the quiz and facts in one transaction, preserving the previous row on failure. The database is `data/movie-content.db` and is ignored by Git; a new checkout must run preparation before it has saved content.

## Counts, uniqueness and truth

Publication needs at least ten scored questions and five facts. Reflections do not count toward the ten. Exact duplicate IDs/text and duplicate answer choices are rejected. This does not detect every paraphrased duplicate or establish whether a fact is interesting; those still need human review or richer evals. Reviewed source-phrase checks support this fixed bank, not arbitrary generated claims.

Missing content returns a coverage message, with no generation attempt. Spoiler permission gates saved content as well as live answers. There is no automatic regeneration button or public write endpoint.

Development React Strict Mode can start and cancel a read during mount checks. Multiple GET reads do not generate content; replay sends no read request. Model token use for saved-content reads is zero.


## Questions and answers

**Why not keep the collection in a dictionary?** A dictionary disappears on restart; SQLite writes it to disk. The same published collection can serve every viewer without another model call.

**Why save quiz and facts together?** One transaction prevents half-published collections. The old collection stays intact until the complete replacement passes validation and commits.

**Does persistence make an answer correct?** No. It preserves errors as well as correct content. Evidence checks and review must happen before publication, and corrections require an explicit replacement.

**Where will the preparation agent go?** Between source collection and publication. It can propose facts/questions and explanations; the validator and publisher still decide whether the complete collection can become visible. Browser reads never call that agent.

Verification: 233 backend tests and 21 browser journeys pass; build passes. The real saved collection completed 10/10, replay reset to 0/10, reload returned identical content, and mobile had no overflow/page errors.

## Explicit expansion — 2026-10-10

The saved starter is still read automatically. **Generate more questions** is a separate explicit action: the browser POSTs `/quiz/more`, local Ollama proposes up to three questions from the saved plot excerpts, the backend checks them, and accepted items are appended to SQLite. Your existing answer selections are retained; reload returns saved additions. This action can take longer and requires Ollama. Reading the quiz never runs generation.

Each proposal must have four distinct options, a valid answer index, a known passage ID, an exact evidence quote, and its correct option in that quote. Exact/near-identical question wording is rejected. Explanation text is the verified quote rather than unrestricted generated prose. These checks do not prove every question’s reasoning or every distractor’s correctness, and they do not detect all semantic duplicates; human review and labelled generation evals remain necessary.

A shared model slot avoids competing AI calls; requests have a 90-second deadline and a three-question proposal limit. The collection holds at most forty items. A timestamp check prevents an older generation from overwriting a newer publication. Failed requests do not overwrite saved content. The generated items carry `origin=generated` in the API/storage.

The UI hides evidence for correct answers, offers it after wrong answers, and labels interpretations as unscored. Wrong answers identify the correct option letter and text.

Generation quality update: the first unrestricted prompt produced duplicate/unsupported proposals and was rejected. Generation now allocates unused reviewed story details, selects complete matching sentences, and asks Ollama to write question stems and distractors around known supported answer phrases. Topic IDs prevent the same allocated detail from being reused. This is bounded, source-guided generation, not an unrestricted movie quiz agent. After a topic's question is accepted it is saved; source/topic coverage is finite and exhaustion disables further generation.

Human review of real-model output caught one ambiguous question from a truncated sentence and one incorrect causal question (awakening **from** cryostasis versus awakening **using** it). Both were removed from the live collection. Complete-sentence selection and a regression for the known state/cause error were added. Four supported additions remain saved from these runs. The review records preserve the rejected results; do not report all raw proposals as accurate. Automated source membership checks alone did not catch these errors.
