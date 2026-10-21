# 47 — Production facts from interviews and craft articles

## What now works

Arrival has seven saved facts and its original ten quiz questions. Two additional facts came from a TIME filmmaker interview and a BFI article about Denis Villeneuve's craft. They include source excerpts and dated reading links. The implementing assistant inspected the proposed claims before choosing them; this is not independent human review or automatic publication.

This delivery adds a reusable article pipeline with two reviewed mappings for one film. It does not automatically prepare the remaining catalog. Wikipedia and script-based story workflows retain their separate boundaries.

## Follow the data from website to UI

1. `background_registry.py` defines the exact movie, URL, expected headline, publication date, author and reviewed background paragraph prefixes.
2. `background_articles.py` fetches bounded HTML and parses the first visible article. It verifies structured metadata and keeps only the registered complete paragraphs. Script, navigation and caption content is excluded. No JavaScript runs and no linked page is followed.
3. The resulting `SourceDocument` contains normalized text, contiguous section spans, a revision and source identity. Each section has a code-assigned background category.
4. `background_fact_workflow.py` indexes that source using local embeddings, retrieves two relevant chunks per article and trims them to complete source sentences. Exact origins link the context back to the snapshot.
5. Ollama proposes up to two facts per article. A separate critic checks the proposal. This creates an internal inspection report, not a user-facing draft or published collection.
6. An explicit selection file pins chosen candidate IDs to the report's SHA256. The publisher rechecks the report, source snapshots, quote support, duplicates, limits and the collection timestamp before saving.
7. The existing facts endpoint reads SQLite. The React facts panel validates the response with Zod and displays the saved facts and reading links.

The writer and critic are ordinary asynchronous Python functions making HTTP requests to local Ollama. No LangChain knowledge is required to understand this workflow.

## Why register paragraphs instead of trusting an entire website?

The BFI page discusses several films. A publisher name alone cannot establish that every paragraph describes Arrival. The registry selects a specific music paragraph whose surrounding article context was inspected. The TIME page mixes plot, photography captions and production discussion; only three reviewed background paragraphs enter this pipeline.

Matching a title, date or prefix verifies an identity and extraction contract. It does not prove everything a publisher says is true. Refreshes still need review, especially if selected text changes while its prefix stays the same.

Publication dates come from article metadata; retrieval time records when the app read the page. They answer different questions. A 2017 interview should not appear as new 2026 reporting simply because we fetched it today.

## Why source-sentence IDs fixed a real failure

In the first run, the model changed curly apostrophes to straight ones while copying evidence. The claim looked plausible but failed exact source matching. Another proposal copied a BFI sentence almost word for word.

The revised writer returns a record like this authored example:

```json
{
  "facts": [{
    "title": "A practical lighting choice",
    "text": "The crew relied on a reusable rig to light the set.",
    "support_id": "S2"
  }]
}
```

Code maps `S2` to an already extracted sentence and attaches its exact original bytes, passage ID and citation. The model cannot choose a URL, edit the quote or supply a publication command. Unknown IDs and extra fields fail validation. A long copied prose span also makes a candidate ineligible.

This solves quote ownership, not semantic truth. A genuine source sentence can still be paired with an unsupported claim. The critic rejected one revised proposal for combining a mood-board claim with a quote that only established an artistic influence. Manual comparison with the complete background paragraphs remains part of this release's publication procedure.

## Three separate saved layers

| Layer | Contents | Reuse |
| --- | --- | --- |
| Private article cache | Original HTML, retrieval time, body hash, registry fingerprint, extraction version and evidence revision | Explicit refresh; corrupted/stale cache fails instead of silently fetching |
| Chroma evidence store | Source chunks, local embeddings and exact movie/revision metadata | Same evidence/model/chunk settings reuse the complete snapshot |
| SQLite content store | Final facts, quiz, citations, reading links and source manifest | Normal page reads call neither the model nor article publishers |

HTML changes caused only by unrelated ads/assets can change the raw content hash without changing the extracted evidence revision. Refresh publication still verifies the exact inspected raw snapshot. Old reports do not silently authorize a refreshed source.

## What the safety boundaries do

- Only the two exact registered article URLs are allowed by this integration and the frontend contract. Publisher lookalikes and arbitrary user/model URLs are rejected.
- Fetching uses fixed HTTPS clients, disabled redirects, time/byte limits and no page traversal.
- Evidence remains movie-scoped and background-only. These article facts are not wired into plot quizzes.
- Local model calls have typed responses, bounded output and no shell, filesystem, network or database tools.
- Model acceptance is insufficient to publish. The explicit selection is trusted developer/operator input, bound to an inspected report. Its hash is a change detector, not an authentication signature or user permissions system.
- SQLite compares the previous preparation timestamp when saving. A competing change makes the stale write fail. Existing quiz and facts are retained.

Article fetching uses `asyncio.TaskGroup` for two independent read-only requests. Local embedding/writer/critic calls stay sequential. This is controlled tool orchestration; it is not a demonstration of several autonomous agents browsing freely. The offline CLI is intended to run separately from interactive inference; the existing web inference lock does not coordinate separate processes.

## Observed results and limits

The initial inspection proposed three facts, with one eligible for review and two rejected for altered quote bytes. A second iteration fixed quote ownership but still had one unsupported combined claim rejected. The final inspection proposed four eligible facts in 46.80 seconds; two were selected after assistant inspection for novelty and useful detail. Two remained unsaved. Eligibility and inspection counts are not accuracy scores.

The second cache/index check reused both saved source and vector snapshots. Its retrieval/index stage took 0.10 seconds and performed no fact generation. This duration excludes the initial setup, cache-read phase and network fetching; it is not an end-to-end latency benchmark.

Fresh API reads show seven facts, ten quiz questions and two reading links. Existing Inception quiz qualification remains enabled. There are 728 passing backend checks, including 49 new article/publication checks; nine relevant browser journeys and the frontend build pass.

Reports: `evals/movie-rag/background-articles/`. These are development inspections and operational checks. No unseen-movie fact-quality benchmark was added here. The ASC pages rejected ordinary automated fetching and were not integrated; no bypass was attempted. More film mappings, stronger fact-quality evaluations and background jobs remain next work.

## Run it locally

From `backend`, with the reviewed local models installed:

```sh
# Read the reviewed publisher URLs explicitly, index, propose and critique.
PYTHONPATH=src .venv/bin/python scripts/prepare_background_facts.py \
  --refresh --report ../evals/movie-rag/background-articles/new-inspection.json

# Reuse existing article and vector snapshots; no chat generation.
PYTHONPATH=src .venv/bin/python scripts/prepare_background_facts.py \
  --index-only --report ../evals/movie-rag/background-articles/cache-check.json
```

Publication is a separate mode using `--selection path/to/selection.json` and its matching `--report`. Do not replay the delivery's old selection: the collection has changed since that inspection, so its stale write is rejected. Inspect new outputs against their original context first.

## Questions and answers

**Is RAG involved even though we already chose the article?** Yes. Article selection identifies a source; retrieval selects bounded evidence from its indexed text before generation. A retrieval score estimates relevance, not truth.

**Why can't we let the model pick URLs?** The code currently owns source identity, publisher metadata and action permissions. A model-picked URL would expand the fetching boundary and need its own discovery, URL-validation and evaluation design.

**Do we fetch news when someone opens Facts?** No. The page reads the saved SQLite collection. Refresh, generation and publication are explicit preparation operations.

**Did passing the tests prove the facts are correct?** No. Tests exercise boundaries, recovery and persistence with authored fixtures. The real-model inspections reveal actual outputs; source comparison assesses their claims. Broader independent evaluations are still needed.

**Why keep unsaved and failed proposals?** They show where generation, retrieval or review failed. Reporting only published facts would conceal the cost and rejection rate of the workflow.
