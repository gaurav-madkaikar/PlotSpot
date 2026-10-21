# Multi-movie discussion and feature availability

Approved roadmap slice: extend evidence coverage across the ten starter films while preserving reviewed content boundaries.

- Add explicit TMDB-ID-to-Wikipedia-title mappings for the starter films; validate them against real API responses.
- Keep retrieval strictly scoped to movie ID, source revision and spoiler consent; retain one model slot. Cache at most ten source documents independently with a five-minute TTL.
- Add a read-only feature availability endpoint: discussion derives from reviewed mappings; saved quiz/facts derive from validated published collections. No Wikipedia/Ollama calls or source preparation happen in this endpoint.
- Load availability once per movie page through React Query. Panels show loading/retry or unavailable states; a failed optional availability request does not hide metadata.
- Remove Interstellar-specific question text/feature gates from panels. Source-supported movies get discussion; unprepared quiz/facts remain explicitly unavailable.
- Validate source mapping, cross-movie isolation, cache reuse, consent-before-I/O and inventory failure handling. Exercise another movie with actual local Ollama and save measured output/learning notes.

No automatic quiz/fact generation, unrestricted article discovery or public discussion posting. Expanding prepared quiz/fact banks and semantic discovery remain separate pending slices.

Completed: ten actual source checks; 289 backend tests; 27 browser tests; build; two real local-model checks and Arrival live-page verification. Saved Interstellar content retained.
