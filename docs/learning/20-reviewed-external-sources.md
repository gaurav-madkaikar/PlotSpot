# 20 — External sources and screenplay provenance

## What you can see

Interstellar now has six saved background facts. The new fact is about the visual-effects renderer being adapted for scientific research. The Facts tab also links to the team's published account and a clearly labelled 2008 screenplay draft. Your saved quiz questions are preserved.

## Data flow in simple terms

`Reviewed source ID → bounded API/page read → identity/version checks → source metadata → reviewed claim → atomic SQLite publication → frontend validation → facts and reading links`

The browser reads SQLite through our existing Facts endpoint. It does not fetch Caltech or IMSDb, and viewing does not call Ollama. Ollama continues to power Discuss and optional question expansion. This slice deliberately adds trusted source plumbing and one reviewed claim; it does not implement an autonomous web researcher.

## The Caltech API call

`external_sources.py:fetch_caltech_article` sends a GET to the fixed URL:

`https://authors.library.caltech.edu/api/records/awp8p-s4d82`

The response is JSON. The relevant fields are:

```json
{
  "id": "awp8p-s4d82",
  "metadata": {
    "title": "Building Interstellar's black hole: the gravitational renderer",
    "description": "The article abstract ...",
    "publisher": "ACM",
    "publication_date": "2015-08",
    "creators": [{"person_or_org": {"name": "James, Oliver"}}]
  }
}
```

The actual record has five authors. CaltechAUTHORS hosts the record; ACM is the recorded publication publisher. We retain that distinction.

The adapter checks the exact record ID and title, bounds the abstract, and records authors, date, fetch time and SHA-256 of the response. It wraps the abstract in a SourceDocument tagged as effects. That record can use the same section-aware chunking/embedding infrastructure later; this slice compiles a reviewed fact directly, without embedding or generating it.

`external_content.py:compile_external_fact` checks for the reviewed supporting statement and renderer name before emitting the predetermined short claim. This is evidence-backed curated publication. It does not prove arbitrary model-written facts are true.

## The screenplay check

`fetch_script_provenance` reads the fixed IMSDb page with a bounded response and parses only the first 2,000 characters of its screenplay `<pre>` header. It verifies the title and the expected March 12, 2008 date. The full response is transiently read to calculate a hash, but the application persists only provenance and a reading link, not the screenplay.

This mapped script always has `eligible_for_quiz=False`. It is not converted into plot passages and cannot be used as a QuestionCitation. A changed title/date requires review instead of being silently treated as the released film. We have not verified a final-film screenplay.

## Why a revision manifest?

Originally every question/fact cited one Wikipedia revision. Now the quiz still cites Wikipedia while the new fact cites a Caltech snapshot.

A manifest records each evidence revision and its exact source URL:

```text
Wikipedia extraction revision → Wikipedia oldid link
Caltech response hash revision → reviewed Caltech record link
```

ContentStore validates that every citation matches this manifest and that no extra or missing revisions are present. The manifest lives in the existing JSON payload, so old collections can load without a database schema migration. New mixed collections require an explicit manifest. Question expansion carries the saved manifest forward instead of trying to republish everything as Wikipedia-only.

Publication uses the existing timestamp comparison: if another operation updated the collection while source fetching was in progress, this operation fails rather than overwrite newer questions. Both sources must succeed before any publication. A failure leaves the old collection intact.

## Guardrails and their limits

- Code-owned exact URLs; no browser/model-supplied fetch URL.
- Fixed HTTPS hosts, redirects disabled, environment proxies disabled in production clients.
- Streaming response limits: 200 KB Caltech; 1 MB IMSDb; 30-second client timeouts and a 65-second preparation deadline.
- Exact article identity and screenplay header/version checks.
- Citation URLs validated on both backend and frontend; the early draft is reading-only.
- No fetched page commands are executed. The claim compiler copies only a reviewed supporting statement; it has no shell, write-tool or model capabilities.
- Output remains text rendered by React, never arbitrary source HTML.

These controls constrain this adapter. They are not a general guarantee against all prompt injection or false claims. The draft date/header is a provenance check, not an independent authenticity proof; the source title is not a general wrong-movie classifier.

## Run the explicit preparation

From `backend`:

```sh
.venv/bin/python scripts/prepare_external_sources.py
```

If the fact and links already exist, it makes no network/model calls. `--refresh` rechecks the two reviewed sources and updates that external fact/link metadata while preserving the quiz and other facts. This differs from `prepare_movie_content.py --refresh`, which explicitly replaces the whole starter collection.

## Questions and answers

**Is fetching an article RAG?** Fetching alone is ingestion. RAG additionally retrieves relevant evidence and supplies it to a model. The existing Discuss feature does that; this reviewed fact publication does not need a model.

**Why not let the agent browse any URL?** We first need observable, tested source adapters. A future search agent can propose candidates, but candidate discovery should not bypass the fetch policy or publication checks.

**Why hash the response?** It identifies what was fetched when the publisher has no Wikipedia-style revision ID. A hash detects change; it does not certify truth, and the publisher's live link may later show updated content.

**Why are script and fact sources different?** A production account supports a background claim. An early screenplay supports studying that draft; it cannot automatically support claims about the released movie.

**What do these evals compare?** Labelled cases expect acceptance/rejection for wrong titles, changed draft dates, unknown URLs, redirects, oversize responses, injected commands, manifest mismatches and failed refreshes. They check system behavior, not similarity-score thresholds. Browser checks verify links, labels, spoiler gating and mobile rendering.

Verification: 284 backend tests, 24 browser tests and frontend build passed. The real-source report is `evals/movie-rag/external-sources-smoke.json`. A separate real-page check confirmed six fact cards, all saved quiz items, and no mobile horizontal overflow or page errors.
