# Movie trailers and creative credits

**Goal:** Implement the approved second movie-page phase: a click-to-open trailer and credited writers, composer and cinematographer.

**Architecture:** Append TMDB videos to individual detail reads, map exact crew jobs and a validated YouTube trailer into the existing optional metadata, and persist it in SQLite. Track presentation completeness so old saved detail records enrich once. Keep bulk semantic imports free of video requests. Render a native dialog with no video iframe before a click; closing removes it. Missing or unsupported media does not invalidate core movie metadata.

**Constraints:** No invented creative roles, arbitrary embed URLs, automatic playback on page load, new packages or adult exclusions. Official trailers outrank unofficial ones; teasers/clips are not passed off as trailers. Existing last-good fallback and seven-day freshness stay in place. Use keyboard-accessible dialog controls and source attribution. Preserve older API payload compatibility.

- [x] Add typed presentation metadata, bounded selection/mapping and upgrade-aware saved reads.
- [x] Add a trailer dialog and creative-team cards using current design tokens.
- [x] Test malformed videos, exact role mapping, old-cache enrichment, negative results, saved reuse, click-only media, Escape/focus and missing fields.
- [x] Run backend/browser checks, restore live servers and record learning notes and a preview.

Validation: 427 backend checks, 44 browser journeys and production build passed. Live Inception trailer played successfully and was closed. Creative credits and trailer persisted in SQLite; live servers restored.
