# Automatic search and broader content coverage

User-authorized implementation, continuing the existing shared checkout.

Goal: remove redundant search invitation copy, update keyword results after a 350 ms typing pause, and increase complete saved fact/quiz collections from four to six films.

Architecture: debounce only the URL query update; React Query continues to own API response cancellation/cache identity. Preserve filter/page navigation and legacy external filmography lookup. Add authored, evidence-reviewed movie banks through the existing versioned Wikipedia compiler and explicit publication command; no automatic unreviewed generation. Existing local Ollama/RAG workflows and their qualification gates remain intact.

- [x] Search: remove invitation sentence; debounce typing with replace-history, cancellation, IME support, immediate Enter, filters preserved and page reset. Browser-check coalescing, stale responses and navigation.
- [x] Coverage: inspect registered released-film sources for Knives Out and The Truman Show; author ten distinct scored story questions and five production facts per film. Freeze private source snapshots and publish only after exact source/compiler validation. Preserve existing collections.
- [x] Validation: extend backend contract checks across new films, verify repeat live reads and feature inventory, build frontend and run focused browser journeys. Document real coverage, source revisions and learning flow.

Interpretation: broader coverage means useful movie-page facts/quizzes, previously limited to four films; metadata discovery already has over 1,500 films. Curated starter banks remain explicitly authored, rather than being misrepresented as generated AI output.

Delivered: six complete saved films; new films each have 5 facts/10 questions. Fixed revisions, content hashes and live checks are in evals/movie-rag/coverage/live-publication.json. Original four hashes unchanged. 738 backend tests, affected browser journeys and production build pass. Optional name lookup is a compact link.
