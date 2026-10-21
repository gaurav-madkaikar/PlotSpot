# Lesson 14 — fetch a real, attributed movie source

## What you will learn

Your pipeline accepts SourceDocument records, but until now they were fictional. This slice fetches an English Wikipedia article and turns its response into the same source shape. You write the HTTP request; the assistant handles validation, text conversion, attribution and revision identity.

```text
Reviewed movie ID → Wikipedia article title
                        ↓
Your GET request → JSON containing article HTML and revision ID
                        ↓
Assistant mapper → plain text + source reference + revision + unknown spoiler label
                        ↓
Later: reviewed sections → your ingestion helper → stored evidence → movie-page answers
```

The starter supports one explicit mapping: TMDB movie ID 157336 → `Interstellar (film)`. It is not a general Wikipedia search or title-matching service. We will expand reviewed mappings and source selection separately. The webpage is unchanged by this exercise.

## Your coding slice

Implement `request_article` in `backend/src/movie_companion/wikipedia_source.py`. It receives an existing HTTPX client and a reviewed article title. Use that client to GET `/w/api.php`, passing this dictionary through `params=`:

| Parameter | Value | Purpose |
|---|---|---|
| `action` | `parse` | Return parsed article content |
| `page` | the supplied `title` | Select the reviewed article |
| `prop` | `text\|revid` | Request HTML and its revision ID |
| `format` | `json` | JSON response |
| `formatversion` | `2` | Modern response shape with a direct text string |
| `disableeditsection` | `1` | Omit edit-section links |
| `disabletoc` | `1` | Omit the table of contents |

The pipe character in `text|revid` separates requested properties; it is just part of a Python string. Return the HTTP response. Do not parse it, create another client, fetch arbitrary URLs, request embeddings, or generate an answer here. The surrounding `fetch_movie_source` wrapper handles status and response validation.

See the [official MediaWiki parse API](https://www.mediawiki.org/wiki/API:Parsing_wikitext) for the parameters and content/revision behavior.

## GET versus your earlier POST requests

Ollama requests used `client.post(..., json=...)` because we supplied structured inference input in the request body. This read-only Wikipedia request uses `client.get(..., params=...)`, putting named query parameters into the URL.

HTTPX encodes spaces, parentheses and special characters in the supplied title. You do not need to manually concatenate or escape the URL. The caller supplies the fixed `https://en.wikipedia.org` client, timeout and identifying User-Agent.

The pattern is the same async idea you already know: an awaited request returns a response object. Your function returns that object to its caller, where the assistant's wrapper calls `raise_for_status()`, reads JSON, and maps the data.

## Response format

Simplified illustrative shape, with made-up content/revision:

```json
{
  "parse": {
    "title": "Interstellar (film)",
    "pageid": 6009939,
    "revid": 12345,
    "text": "<p>Article content appears here.</p>"
  }
}
```

The response itself is JSON; the `text` field inside it is HTML. These are separate formats. Our standard-library HTMLParser extracts readable text and does not execute scripts or render HTML. Script/style text is excluded, but prose instructions remain untrusted source data. Stripping tags is not prompt-injection prevention or a guarantee of factual accuracy.

The mapper records an `oldid` permalink for the returned revision. Its revision string also includes `plaintext-v1`, identifying our extraction representation. Chunk offsets later refer to that normalized plain text, not positions in the HTML or Wikipedia's rendered page.

## Assistant-owned boundaries

- Only the explicitly reviewed movie mapping and fixed HTTPS provider are accepted.
- Redirect following is disabled, and returned article identity must match the mapping.
- Missing pages/API errors, wrong identity, missing revision IDs and unusable content are rejected.
- Buffered JSON/HTML is limited to 2MB; extracted text follows the source record's 100000-character bound. Checking buffered size does not impose a streaming download limit; that belongs to a later transport boundary.
- HTTP failures propagate. There is one request, no automatic retry loop or bypass of provider limits.
- Whole-article spoiler status remains **unknown**. This may include plot material and references; do not relabel it safe merely because it came from Wikipedia.

Wikipedia provides useful attributed background and production context, but this full article is not our dedicated external-news facts feed. Production-section selection, source dates/licensing metadata, film-identity checks beyond the manual mapping, and spoiler review will be added before public source rendering or generation integration.

## Run the exercise

From `backend`:

```sh
.venv/bin/pytest tests/test_wikipedia_source.py -q
```

The starter has 14 cases: one request-contract case intentionally awaits your function, while 13 assistant mapping/boundary cases pass. Tests use authored fixtures and a mock transport, without internet or Ollama.

After implementing the request:

```sh
.venv/bin/python scripts/try_wikipedia_source.py
```

This makes one real internet request and prints source attribution, revision, text length and spoiler status. It does not ingest the article, display story text, or call any model. API availability or rate limits can make the real call fail even when contract tests pass.

If you deliberately want a potentially spoiler-containing preview:

```sh
.venv/bin/python scripts/try_wikipedia_source.py --show-text
```

No preview is needed to complete the API exercise. Default output is metadata only.

## Preparation evidence

A separate assistant transport preflight returned HTTP 200 for Interstellar (film), with integer page/revision IDs and an HTML string. The learner's request helper remains a stub at preparation, so that preflight is not a completed learner implementation or source-to-answer result. No article was automatically ingested or used for generation.

## Concepts to explain afterwards

1. Why use `params=` for this request instead of Ollama's `json=` body?
2. How can a JSON response contain HTML?
3. Why retain the article revision rather than just its current URL?
4. Why does removing HTML tags not make the evidence safe or truthful?
5. Why keep an unreviewed movie article's spoiler status unknown?

## Completed review — 2026-10-10

Your request correctly awaits the supplied client's GET, supplies the required parameters, and returns the response. Calling `raise_for_status()` here is harmless; the wrapper also checks it. All 188 backend tests passed before the movie-page integration was added.

The real metadata-only run returned:

```text
Source: English Wikipedia contributors: Interstellar (film)
Reference: https://en.wikipedia.org/w/index.php?oldid=1379200125
Revision: enwiki-1379200125-plaintext-v1
Characters: 93088
Spoiler status: unknown
```

This run fetched and mapped the article, without model inference or ingestion. Later requests can return a different revision and length. The following app integration uses the whole article only with explicit spoiler permission; production-section selection remains future work.

### Concept answers

1. `params=` encodes named values in the GET URL. Wikipedia's parse endpoint reads these query parameters. Ollama reads inference input from a POST JSON body instead.
2. JSON is the outer container. Its `text` value is a string containing HTML, just as another JSON value might contain ordinary prose. We parse the JSON first, then extract text from that HTML string.
3. The current article can change. A revision permalink identifies the particular version used for an answer; its revision also helps invalidate our persistent evidence cache when the source changes.
4. Removing tags prevents us from treating source HTML as executable UI. False claims and instructions such as “ignore your rules” can still appear as plain text. The grounding prompt treats them as untrusted evidence; the model has no action tools here. Citation membership still does not prove a claim is supported.
5. A full movie article may contain plot details. “Unknown” keeps that uncertainty explicit and lets the application require spoiler permission before fetching or generating from it.
