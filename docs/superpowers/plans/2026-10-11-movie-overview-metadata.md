# Movie overview metadata implementation

Scope authorized by the user: populate a lively, consistent light movie overview with production companies, release date, languages, budget/revenue, average ratings and actor-character pairs. Reviewed the user's open TMDB Credits/Details documentation in Chrome. Existing adult-inclusion policy continues.

Design: a full-width Film details card with a rating tile, compact metadata grid and production tags, followed by Cast & characters portrait cards. Replace the former explanatory sidebar. Use TMDB attribution, USD labels and truthful missing-value states. Spoken languages and the top-level release date have distinct meanings from regional release editions.

- [x] Add optional versioned MovieMetadata/CastCredit contracts; retain existing cast names.
- [x] Normalize existing details/credits response in movie_metadata.py; validate image paths, dates, money and ratings.
- [x] Add one-time on-view enrichment for legacy SQLite records; retain fresh reuse and last-good fallback. Preserve richer nested fields on incomplete refresh.
- [x] Maintain existing semantic snapshot fingerprint compatibility for absent metadata.
- [x] Validate optional metadata in Zod and implement MovieOverview with responsive light styling, portrait fallback and actor roles.
- [x] Test provider mapping, incomplete data, legacy cache enrichment/reuse/failure and richer refresh preservation; build and run browser coverage.
- [x] Verify live Inception metadata and the expanded view; restore local servers and record final outcomes.

Learning note 31 explains the end-to-end flow and API field semantics. No bulk backfill, new external rating provider, model generation, commit or deployment is part of this change.


Final validation: 416 backend tests, 40 browser journeys, production build and live Inception persistence/reuse passed. Live overview visibly shows rating/votes, release date, four spoken languages, production companies/countries and USD finances, plus twelve actor-character portrait cards. Inception remains open in the app browser. Screenshot: .cache/previews/movie-overview-metadata.png. The existing 1,500-movie semantic snapshot and fingerprint are unchanged.
