# Movie page sections implementation plan

**Goal:** Implement the approved first phase of the movie-page redesign: one scrolling page, section navigation, a prominent rating, compact spoiler preference, and consistent light sections.

**Architecture:** Keep the current movie API contract. Render stable About/Cast/Facts/Quiz/Discuss anchors. Observe sections to highlight navigation; mount feature panels when near the viewport or requested by a hash. Once mounted, retain panel state until the movie or spoiler preference changes. Existing saved-content endpoints keep their permission checks.

**Constraints:** Preserve local collection state and source attribution. No new dependencies, automatic content generation, provider integrations, or adult filtering. Keep keyboard focus visible and sticky navigation clear of section headings. Respect reduced motion. Preserve unrelated worktree changes.

- [x] Split cast and production details into separately placed sections; move rating to the header.
- [x] Add section navigation, hash loading, viewport-triggered feature mounting and compact spoiler preference.
- [x] Update browser journeys from tabs to links, add deep-link/lazy-loading/state-retention coverage, build and verify mobile/desktop.
- [x] Record learning notes and a live screenshot.

Trailers, additional creative credits, watch providers and related films are subsequent phases; this change does not present unavailable data.

Validation: production build passed; all 42 browser journeys passed, followed by 11 focused checks after adding repeated-anchor and quiz-retention assertions. Live Inception cast/navigation visually verified; servers restored.
