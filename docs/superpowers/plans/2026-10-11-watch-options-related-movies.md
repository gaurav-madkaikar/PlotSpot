# Watch options and related movies

**Goal:** Implement the approved final movie-page phase: regional watch availability and related movie tiles.

**Architecture:** Add independent read-only endpoints for regions, a selected country's watch options and six TMDB recommendations. Persist normalized responses in a bounded SQLite cache, separate from core metadata and semantic vectors. Watch options expire after six hours, recommendations after one day and regions after seven days. Bounded last-good fallback is explicitly labelled stale. Unknown availability is never described as a guarantee that a film cannot be watched.

**UI:** Keep the light editorial style. Put Where to watch after film details and More like this below discussion. Use the existing viewport-triggered mounting for independent requests. Country selection defaults to India and is editable, without location detection. Show subscription/free/with-ads/rent/buy categories, valid provider logos, and the supplied TMDB watch link with JustWatch attribution. Related tiles show poster/title/year and navigate to full details on click. They do not require six extra detail requests.

**Constraints:** Exact movie/country cache keys, provider response validation, bounded records, only validated TMDB image/link URLs, no fabricated prices/direct provider deep links, no adult filtering or LLM calls. Preserve existing page and navigation behavior.

- [x] Implement typed provider normalization and bounded durable cache with independent endpoints.
- [x] Add country selector, watch groups/attribution and related film tiles with loading/error/empty/stale states.
- [x] Test country isolation, cache TTL/fallback, invalid identities/URLs, record bounds, UI selection races, missing data and related navigation.
- [x] Run backend/build/browser validation, restore live app and record learning notes and screenshot.

Validation: 444 backend tests and production build passed. Full browser run passed 47/48; corrected the remaining test to await detail-page navigation instead of matching a tile heading, then all four extras journeys passed in the focused rerun. Across these runs, all 48 browser journeys passed. Live Inception displayed India provider groups, a valid supplied watch link and six related movie posters. Servers restored; learning note 34 and ignored preview screenshots recorded.
