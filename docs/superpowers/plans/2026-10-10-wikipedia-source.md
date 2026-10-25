# Wikipedia Source Connector Pairing Plan

**Goal:** Replace fictional source input with a revision-attributed, read-only real-source fetch for one explicitly mapped movie.

**Architecture:** Learner writes one GET request returning an HTTPX response. Assistant wrapper restricts the host and movie/title mapping, validates HTTP/JSON/identity/size, extracts plain text from HTML without executing it, and creates an unknown-spoiler SourceDocument with a revision permalink. No automatic generation, ingestion, spoiler classification or UI changes in this slice.

**Tech Stack:** Existing Python 3.12, HTTPX, standard HTMLParser, pytest. No API key or new package.

## Ownership and limits

Initial mapping: TMDB 157336 to English Wikipedia `Interstellar (film)`. This is a reviewed teaching mapping, not a general title resolver. One request, fixed HTTPS host, no redirects, timeout supplied by caller, HTML/JSON payload limit 2MB and plain text limit 100000 characters. Size is checked after the buffered response; streaming transport limits remain future work. Unknown spoiler status prevents use in spoiler-free retrieval. Full articles mix plot, production and references; they are not the dedicated news-facts source. Normalized plain-text offsets refer to this extraction version, not original HTML.

## Tasks

- [ ] Create `wikipedia_source.py`: request stub, parse-response helper, plain-text extractor, scoped fetch wrapper. Reject missing/changed identity, errors, absent revision, invalid content and oversized payloads.
- [ ] Add fixture tests for the HTTP contract and wrapper guards, without real network calls.
- [ ] Provide `try_wikipedia_source.py`, printing source identity/revision and length by default; text preview requires `--show-text` so unclassified story content is not shown accidentally. No Ollama or persistence call.
- [ ] Write lesson 14 with GET parameters, actual response shape, source provenance, HTML parsing, spoiler boundaries, and future ingestion integration. Verify expected starter failures and passing assistant/previous cases.

Read-only transport preflight succeeded before scaffolding: HTTP 200, title Interstellar (film), integer pageid/revid, and HTML string. No LLM inference or user-owned request-helper success is claimed by that preflight.
