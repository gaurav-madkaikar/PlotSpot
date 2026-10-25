# 19 — Keep story and production evidence separate

## The problem

Imagine a document whose Plot section ends at character 900 and whose Cast section starts there. A 600-character chunk starting at 700 used to contain both sections. Even a good similarity score could return production information to a story question.

The fix happens before the LLM: preserve headings, stop chunks at section boundaries, and filter eligible categories before ranking. This is a retrieval constraint, not a prompt asking the model to behave.

## How the pieces connect

1. `wikipedia_source.py` reads HTML headings and produces cleaned text plus section spans. Each span has `start`, `end`, `title` and `category`.
2. `SourceDocument` in `evidence_store.py` validates that spans cover the text without gaps or overlaps. JSON snapshots can be loaded back into these validated records.
3. `source_sections.py:source_chunks` calls your existing `chunk_text` separately inside each section. It translates the resulting offsets back to positions in the whole document. Your window/overlap algorithm remains the inner mechanism.
4. Chroma stores each passage's section title/category alongside its movie ID, source revision and embedding. The snapshot fingerprint includes section metadata and the chunking policy, so old vectors cannot silently stand in for differently classified chunks.
5. `prepared_content.py` searches only Plot chunks for starter questions/reflections and only background categories for facts. Missing evidence stops publication. Internal live quiz/fact helpers use the same categories before calling your learner retrieval/LLM pipeline.
6. Discuss can search every section. A viewer's question might be about cinematography, the ending, or the soundtrack, so restricting every discussion to Plot would remove useful evidence.

## Example

```text
Plot → story eligible
  Cooper sends a message through the watch.
Production → background eligible
  Development → inherits production
  Visual effects → effects
Reception → other
  A reviewer describes the film.
```

A heading we do not recognize inherits its parent only when it is a subsection. An unknown top-level heading becomes `other`. For example, Production → Practical methods is background, while Reception does not inherit Production merely because it follows it.

This is an explicit heading map, not an AI classifier. It does not prove that every paragraph is relevant, true or spoiler-free. Article layout changes can cause missing coverage; the system should withhold content rather than silently borrow another category.

## What happens to the caches?

The live source has a new extraction revision suffix, `sections-v2`. Chroma prepares a different snapshot for its new chunks/metadata. Existing learner snapshots without sections can still be read as SourceDocument records and indexed, but they are unclassified and cannot prepare new story/fact collections. Previously indexed storage may need re-ingestion to obtain the new metadata.

SQLite holds published questions/facts, independently of retrieval vectors. Reading the movie page still does not call the LLM. The preparation command now retains any existing published version unless `--refresh` explicitly requests replacement. A refresh replaces the entire collection, including generated additions; we have not refreshed your published collection during this upgrade.

## Checks and real-source result

The labelled routing tests check heading inheritance, unknown sections, invalid spans, cross-boundary overlap, Chroma reopening, cache invalidation, and rejecting content assigned to the wrong category. Service tests check that the pipeline receives only eligible evidence.

The actual Interstellar Wikipedia revision 1379200125 produced 27 sections and 197 chunks: 9 Plot chunks and 40 background chunks. All ten starter scored questions and five facts compiled using their correct routes. This verifies source availability and routing for this revision; it does not measure general answer correctness or resistance to every prompt injection.

See `evals/movie-rag/section-routing-smoke.json`. No model call was needed for this extraction/preparation smoke check, and no published content was replaced.

## Questions and answers

**Why filter before similarity ranking?** A passage can mention the same actors or movie in an irrelevant section. Scope first; compare meaning only among allowed evidence.

**Why not just add “use only plot” to the prompt?** A prompt leaves the decision to the model. Filtering keeps excluded evidence out of its context.

**Is this semantic chunking?** No. This is section-aware character chunking. Semantic chunking would also choose boundaries based on meaning; our windows still use character counts within each section.

**Does “production” mean safe to show before watching?** No. Production paragraphs can mention scenes or endings. All sections retain unknown spoiler status, and consent remains required.

**What comes next?** Reviewed external background sources and script provenance, followed by more movie coverage. The Interstellar IMSDb draft must not become authoritative evidence for released-film quiz answers without version review.
