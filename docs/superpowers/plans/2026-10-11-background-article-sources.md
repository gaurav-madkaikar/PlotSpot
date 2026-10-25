# Background article sources implementation plan

**Goal:** Connect reviewed TIME/BFI background sources to Arrival's saved facts through exact provenance, local retrieval, bounded proposals and inspected publication.

**Architecture:** A fixed registry owns movie identity, URL, expected article metadata and selected background paragraph markers. The adapter reads bounded HTML without redirects, validates identity, extracts only reviewed complete paragraphs and saves versioned private snapshots. A CLI indexes those records with the existing local embedding store, retrieves movie-scoped background passages, writes/critics proposals and produces an internal report. A separate explicit reviewed publication step binds selected proposals to the report/source fingerprints and atomically appends facts while preserving quizzes.

**Tech stack:** Python/httpx/HTMLParser, existing Chroma and Ollama embeddings/chat, SQLite, React/Zod contracts.

## Scope and choices

Three approaches considered: open web crawling, broad publisher-domain scraping, and fixed reviewed article mappings. Choose fixed mappings for reproducible source identity and narrower ingestion. General crawling/search discovery is later work. TIME has direct filmmaker interviews; BFI's multi-film craft article requires specifically scoped Arrival paragraphs. Neither whole page is assumed plot-free or spoiler-safe.

User has authorized autonomous implementation, checks and learning notes. Continue in this existing shared checkout, preserving unrelated work. No commits, new threads or redundant approval gates. Consumer UI keeps the existing light facts cards; no draft workspace. Publication review is performed by the implementing assistant, not claimed as independent human review.

## Task 1: fixed article identities, parsing and snapshots

Files: `background_registry.py`, `background_articles.py`, `source_registry.py`, `tests/test_background_articles.py`.

- [x] Register TIME Arrival interview and BFI Villeneuve craft article with stable URL, movie ID, expected title/date/author and reviewed paragraph prefixes.
- [x] Implement HTMLParser collecting JSON-LD and visible article paragraphs; reject wrong title/URL/date, ambiguous/missing paragraphs, oversized body, redirects and missing article boundaries. Ignore script/style/nav/captions; keep exact normalized text and section spans.
- [x] Save atomic versioned private snapshots, validate hashes/movie/registry identity on load, fail stale or corrupted caches rather than fetch implicitly. Refresh only explicitly.
- [x] Test spoofed URLs, changed identities, mixed-film text, hostile markup, cache corruption and stale versions.

## Task 2: retrieval, bounded local proposals and reviewed saving

Files: `background_fact_workflow.py`, `scripts/prepare_background_facts.py`, `tests/test_background_fact_workflow.py`.

- [x] Reuse `ingest_source`, `EvidenceStore` and local embedding helpers. Retrieve only registered movie background snapshots, retain exact citation offsets and limit each proposal passage to 600 characters.
- [x] Feed at most two passages per source to the existing background-only writer and independent critic; validate origins, quote support, existing-topic duplicates and model/code identity. At most two sources, two writer/reviewer batches, no model tools, 240-second overall budget.
- [x] Write nonpublishing metadata/proposal report with pinned source and implementation/model identity. Preserve failure observations and never fill a quota with guesses.
- [x] Add a separate explicit selection JSON containing report SHA256 and accepted item IDs. Revalidate report, persisted source evidence, decision, duplicates and current collection before atomic publication. No public generation/review endpoint.
- [x] Test fabricated citations, wrong-movie reports, rejected/unknown IDs, altered reports/snapshots, stale writes, capacity and preservation of quiz/facts.

## Task 3: live data, UI contracts and learning

Files: facts schema/reading-link contract, facts panel, browser journeys, `docs/learning/47-background-article-rag.md`, progress and eval reports.

- [x] Allow only the two exact reviewed URLs in backend/frontend citation and reading-link contracts; add interview/article types and derive reading labels from source metadata.
- [x] Fetch/index both public articles, inspect actual local-model proposals and manually compare retained text against complete source context. Save only supported, concise, novel facts using explicit reviewed selection.
- [x] Verify fresh API reads show persisted facts and unchanged quiz; existing reads trigger no generation. Check source links/copy in browser and save visual proof.
- [x] Run backend suite, frontend build and relevant browser checks; document measured outputs, manual review, unavailable ASC sources and limited movie coverage.

## Acceptance

Arrival retains at least five facts and ten scored questions, gains inspected background facts with external citations and dated reading links, and its existing quiz is byte-equivalent before/after. A second source ingestion reuses valid private source/vector caches. Failures preserve existing saved content. This is a reusable source integration and inspected example, not automatic publication or broad production quality qualification.

## Delivered observations

- TIME/BFI raw and vector snapshots fetched/indexed and reused. ASC refused ordinary automated fetching and remains unintegrated.
- Three development iterations retained. Final inspection proposed four eligible facts in 46.80 seconds; implementing-assistant review selected two for supported, distinct production detail. No independent human/unseen-movie quality claim.
- Arrival now has seven saved facts, original ten quiz questions and two dated reading links. Publication and fresh API/database agreement verified; Inception quiz gate unchanged.
- 728 backend checks, including 49 new source/publication checks; nine relevant browser journeys and production build passed. Live source excerpt/links inspected and screenshot saved.
- Lesson 47 and progress explain the three caches, exact sentence ownership, local model calls, explicit review and remaining coverage limits. No public draft workspace or automatic publication was added.
