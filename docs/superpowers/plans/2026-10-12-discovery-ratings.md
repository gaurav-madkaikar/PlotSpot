# Discovery ratings implementation plan

Goal: filter discovery by TMDB rating and show highest-rated matching movies first with rated preview cards.

- [x] Add bounded optional vote fields to Movie/MovieNameCandidate, transfer lightweight ratings and centralize authoritative score/tie-break rules in movie_ratings.py.
- [x] Add min_rating to CatalogQuery and both unified public search endpoints, filter eligible movies, rank before pagination and include the threshold in snapshot identity.
- [x] Validate optional compact vote fields with Zod; add a matching frontend score helper, a shared discovery/collection/related preview badge and minimum-rating control with URL/clear/debounce state and responsive layout.
- [x] Verify backend mapping/ranking/filter/pagination/snapshots and affected browser journeys, build, live rated previews and local API restart; update learning notes.

Verified: 1,217 backend tests pass, frontend build passes, 36 search/filter browser checks and 15 ratings/related/overview checks pass (47 distinct cases across both runs). Live Any/8+ responses are ordered before pagination, 8+ excludes lower/unreported scores, and all eleven shared content-bank hashes are unchanged. The local API is restarted; live filter/cards were inspected without changing user collections.
