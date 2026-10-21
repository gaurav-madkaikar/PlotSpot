# Storage and name discovery — agreed boundaries

Approved in conversation on 2026-10-10. This records product boundaries; it does not claim these migrations/fallbacks are implemented.

## Persistent versus on-demand

SQLite will own canonical movie metadata, source records/revisions, preparation jobs, published facts/questions and eventual owner-scoped user/community records. Chroma owns derived evidence vectors/chunks with stable source/movie IDs. The existing discovery JSON snapshot remains readable during migration and serves as export/rollback material.

Persist the searchable catalog: TMDB IDs, canonical/alternative titles, year, synopsis, genres, runtime, language, main cast, director, keywords and provider image URLs. Expanded details are fetched when missing/stale and saved afterward. Images remain provider-hosted. Search embeddings are derived artifacts rebuilt only when their input/model changes.

Persist permitted source snapshots, provenance, chunks, spoiler classification and accepted facts/questions. First-use preparation saves reusable output. Published Facts and Quiz readiness are independent; missing story evidence must not block background facts. Do not pad unsupported content to meet five-fact/ten-question targets. Refresh preserves the last good publication until a replacement passes validation.

Generate personalised discussion answers on demand; no permanent history by default. Keep ranked search/query embeddings/provider responses in bounded temporary caches. Eventual private history requires explicit user scope/consent and ownership checks. Versioned evaluation reports are durable; detailed operational traces have bounded retention and exclude credentials/raw routine private text.

Freshness policy is configurable. Proposed starting intervals: weekly metadata, daily news checks for recently active films, monthly stable plot/source checks. These intervals do not imply a scheduler exists. Ordinary viewing reuses saved data; refresh is preparation work.

## Search scope

Story/mood searches use only the current published local semantic catalog. No external semantic discovery fallback.

Movie-title, actor and director searches may obtain additional validated TMDB results. Actor filmography uses acting credits; director filmography uses crew entries with job Director. Preserve person IDs and distinguish same-name people. Existing local matches do not prove complete filmography; offer broader provider results without forcing the user to pick a search mode.

External results display canonical movie tiles and can open details before AI evidence is ready. Persist hydrated metadata without requiring immediate embeddings, sources, facts or quizzes. External records join semantic search only after a complete derived index publication. Temporary partial provider data must not overwrite richer stored fields with empty values.

A single search bar stays. A confident local title/person match takes precedence; clear genre/story requests retain local routing. Ambiguous unmatched text must not silently be treated as a person or a title: allow explicit name-search intent through a contextual action in the results area. This is an ambiguity escape hatch, not separate permanent search tabs. Movie titles that resemble genres can use the same action.

## Limits and safety

Use fixed TMDB endpoints, server-only credentials, bounded hydration, provider pagination and canonical-ID validation. Preserve genre/language/runtime filters after hydration; filtering a provider page does not establish a global filtered total. Expose incomplete/continuable results through the response contract. TMDB failure preserves available local results and a retryable external-search state.

Story search remains available from the old snapshot during metadata import and index rebuild. No model chooses arbitrary URLs, file paths, actions or database mutations. Facts/quiz source preparation remains a separate later subsystem; accounts/community remain separate later subsystems.
