# Learning 78: Broader evidence before regeneration

The first replacement pass showed that a citation supporting a weak recall question may not support a better narrative question. This stage retrieved broader story evidence for the 33 unresolved replacement targets without fetching new pages or changing the live quiz banks.

## Retrieval

`WebCorpusStore.movie_sources()` exposes immutable, digest-validated snapshots for one movie. It rejects unknown source kinds, corrupted payloads and unbounded source sets.

`quiz_replacement_evidence.py` reads complete sentences only from plot sections. It ranks them against the old question, the replacement brief and the old explanation with bounded BM25 lexical scoring. It limits source and publisher concentration and returns at most eight passages per target.

BM25 answers “which passages share useful terms?” It does not prove that a passage supports the requested relationship. For that reason, a pinned local reviewer receives only the replacement brief and retrieved passages. It must select one or two passages that explicitly establish the requested choice, cause, consequence, relationship or resolution. Missing context is labelled insufficient.

## Results

All 33 unresolved targets had retrieved candidates. Across repeated target-specific searches, the workflow evaluated 887 retained source snapshots and 24,133 complete plot sentences. The semantic reviewer marked 19 targets supported and 14 insufficient.

Assistant source inspection removed three false positives:

- a Forrest Gump pair identified later encounters but not how they redirected his journey;
- a Lion King passage described Rafiki presenting a different child at the ending; and
- an Interstellar passage described Mann’s deception but did not establish the requested booby-trap consequence.

Sixteen targets therefore entered a second writing pass. The writer returned 15 drafts, but only three passed exact deterministic checks and two passed the structured critic. Editorial review retained one Fight Club purpose question for a later combined-bank review. Together with the earlier Lion King candidate, two of the original 34 targets now have provisional replacements. Nothing was published.

## Why most second-pass drafts were withheld

The dominant failure was `selected_answer_not_literal`. The evidence supported the idea, but the writer changed tense, added a preposition, or paraphrased the answer. For example, “providing a path to another galaxy” became “It provides a path to another galaxy.” That sounds harmless to a reader, but the exact-span guard cannot prove it came from the citation.

This is a recall-versus-precision trade-off. Relaxing the guard would increase accepted drafts but would transfer more factual judgment to a fallible model. The safer next design is an answer-span planner: select an exact source substring first, lock it as the correct option, then ask the writer only for the question and distractors. A repair stage can operate on withheld drafts without weakening citation checks.

## What this demonstrates

- Retrieval coverage and evidence adequacy are different metrics.
- A semantic reranker can produce false positives, so source inspection still matters.
- Better evidence does not guarantee contract-compliant generation.
- Deterministic false negatives are visible and measurable rather than silently accepted.
- Cached multi-source RAG can improve a content workflow without live network dependency.

The reports remain proposal-only and contain no publication authority.
