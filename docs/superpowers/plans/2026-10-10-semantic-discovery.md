# Semantic discovery implementation record

Goal: deliver the approved meaning-based recommendation milestone as a visible, bounded first slice.

Architecture: a separate persistent metadata index prepared explicitly from canonical TMDB IDs; deterministic filters, learner-owned Ollama embeddings and cosine ranking; an explicit submit UI beside existing title/cast search. Ten starter films now, with expansion toward the approved 200-film catalog pending. No chat-agent recommendation generation in this slice.

Global constraints: local Ollama, free existing TMDB access, preserve learner helpers and movie evidence store, light editorial UI, honest coverage, no automatic index preparation on browse, no invented IDs. No commit or publication requested.

- [x] Add `semantic_catalog.py`: versioned validated metadata/vectors, model/fingerprint checks, reviewed IDs, atomic publication, separate `data/private` path.
- [x] Add `prepare_semantic_catalog.py`: canonical metadata fetch with bounded provider concurrency; one embedding batch; explicit demo/refresh options; preserve index on failed validation.
- [x] Add `semantic_search.py` and `POST /api/discover`: validated bounded request; filters before cosine ranking; six returned records; query cache, shared in-flight embedding, shared local-AI slot, deadline and sanitized errors.
- [x] Add `semantic-discovery.tsx`: mode control, explicit search/examples, filters, bounded coverage, loading/error/retry/empty states, existing poster tiles. Preserve title/cast and typo search.
- [x] Add deterministic backend cases and browser journeys for filters, bad data, unavailable/busy services, caching, read-only behavior, malicious text with no action tools, mobile and navigation.
- [x] Prepare live ten-film TMDB index and run labelled Ollama development evaluation; save results and baseline limitations under `evals/discovery`.
- [x] Complete browser regression rerun and real live desktop/mobile inspection; restore running app.
- [x] Save final validation counts in README, learning progress and lesson 22.

Final checks: 306 backend tests, 30 browser tests, build passed; real discovery HTTP calls 200; no mobile overflow or browser errors. Desktop/mobile preview files under `.cache/previews`; live smoke report under `evals/discovery/browser-smoke.json`. Backend and frontend restored on ports 8000/5173.
