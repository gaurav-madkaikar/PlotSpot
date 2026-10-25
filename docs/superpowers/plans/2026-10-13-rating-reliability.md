# Rating reliability implementation plan

Goal: prioritize well-supported movie ratings while retaining the user's original score filter and an explicit raw-order option.

- [x] Implement fixed/versioned trusted score and sort mode in movie_ratings.py/CatalogQuery; propagate through local/live ranking, API validation and snapshot identity. Verify weighting, filtering, identities and complete-pool pagination.
- [x] Add the results-row sort control and persistent URL/query state; preserve sorting when clearing filters. Show compact vote counts using the existing rating badge. Keep toolbar and responsive tokens consistent.
- [x] Update explicit stale-cache fixtures, run focused and full backend checks, frontend build and affected browser flows using disposable servers. Compare real local records without source/model calls.
- [x] Restart the local API, verify the running page and both sort modes, preserve shared content banks and document policy/learning/limitations.
