# Multi-source Movie RAG Implementation Plan

**Goal:** Movie-specific web and script evidence across quiz, facts and Discuss.
**Architecture:** A replaceable bounded search adapter, public-HTTPS source reader, strict identity/purpose classifier, immutable shared corpus cache, source-scoped retrieval and existing reviewed content workflow integrations.
**Tech Stack:** DDGS, httpx, SQLite, existing Chroma/Ollama models, FastAPI, pytest/Playwright.

Constraints: preserve the 11 published banks, guest/member/privacy boundaries, script draft labels, background-only facts and exact source citations. No CAPTCHA bypass, insecure TLS, private-network source reads or silent Wikipedia-only success claims.

- [x] Implement bounded DuckDuckGo/Startpage search, URL/DNS-pinned fetching, full-text extraction, strict film identity, purpose separation, immutable snapshot storage and corpus coverage traces.
- [x] Add Wikipedia/web/optional IMSDb collection with caching/singleflight, and scope-safe integration into discussion retrieval, research preparation and additional quiz generation. Preserve source validation and publication review.
- [x] Add deterministic security/relevance/routing eval fixtures and failure/cache/API tests. Run full checks and bounded live acquisition/local-model proof; repair deficiencies exposed by evidence.
- [x] Document configuration, evidence provenance, learning notes and measured limits; inspect the running app and preserve existing shared banks.

Validation: 1,309 backend checks; 29 affected browser cases plus one visual follow-up; frontend build; 12/12 offline labelled source-policy cases. Local discussion and independent quiz-review proof recorded in evals/movie-rag/multi-source. All eleven banks unchanged. API restarted and member boundaries checked.

Qualification limits: production-trivia search/Startpage were unavailable; some retained story pages contain misleading claims. Independent Wikipedia support now gates web quiz retention. A correct ratio was withheld due to missing retrieved reference context. The initial generation run is superseded by that gate; final-policy end-to-end generation/load benchmarking and fresh independent labels remain roadmap work, not completed production claims.
