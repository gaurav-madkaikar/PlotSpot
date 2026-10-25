# Keyword search and movie layout implementation plan

User explicitly requests these changes and has delegated implementation; execute inline without an additional approval cycle or commits.

Goal: metadata keyword search without embeddings/LLM calls, and simplified consumer UI.

- [x] Movie page: remove return link and every Draft workspace rendering; place section navigation immediately after hero actions and before About details/cast, retaining deep links and sticky navigation.
- [x] Search controls: trailing 44px SVG submit button with accessible Search name and loading status; remove leading icon; contain focus inside rounded field, use site selection/autofill colors, retain keyboard focus. Replace mood examples/help with title/person/description keywords.
- [x] Search backend: read validated SQLite metadata independently of vectors, include on-demand saved movies; use normalized literal title/actor/director and all-keyword matches, constrained token-level typo correction, known-identity suggestions and strict filters/pagination. No inferred themes, synonyms, query embeddings or reranking. Preserve optional live TMDB name lookup.
- [x] Director suggestions: bounded known labels with verified movie IDs, align Python/Zod/UI contracts. Correction only when unambiguous; suggestions expose ambiguous matches.
- [x] Disable production semantic discovery route/startup; retain old learning modules as historical exercises, no active UI/API inference route.
- [x] Verify backend regression suite and browser journeys, including no-model searches, typo/ambiguity, stable pages, no draft requests, mobile controls and navigation order. Restart local backend and inspect the live UI.

Search constraints: exact normalized identities rank first; lexical AND terms may match across documented metadata fields, no fabricated descriptions. Literal genre labels can match as metadata; genre filters stay strict. Generic filler words may be ignored only after checking exact identities. Fuzzy words require at least four characters, constrained edit distance and a single best match; no arbitrary nearest-neighbor results. No result is valid when no metadata supports the query. Existing semantic eval reports remain historical, never presented as current keyword results.
