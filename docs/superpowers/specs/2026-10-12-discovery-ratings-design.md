# Discovery ratings

User request: add a rating filter, list highly rated films first and display ratings on movie preview cards, preserving the current design.

Use TMDB vote averages (0–10), never invented demo/IMDb scores. Add optional compact vote_average/vote_count fields to movie and title-candidate contracts so lightweight live results carry ratings without individual detail calls. Existing detail_metadata remains authoritative for hydrated records; old catalog payloads remain valid without migration. Scores without positive vote counts are unreported.

Discovery gets Minimum rating: Any rating / 6+ / 7+ / 8+ / 9+. A supplied minimum excludes unreported ratings. Browse order is rating descending, vote count descending, title and ID for stable ties; search keeps verified identity relevance first and uses rating ordering within comparable matches. Apply filtering and ordering to the whole pool before slicing pages. Unified search snapshot keys include the minimum, so changing it starts a fresh first page. Existing genre, runtime, language, spelling suggestions and person-credit restrictions remain.

Preview cards show a star, one-decimal score and TMDB attribution, or Not rated / Rating unavailable, distinguishing zero votes from absent metadata. Related previews reuse the same attributed badge while preserving recommendation order. The search and four filters share a desktop row; tablet wraps to two filter columns; narrow mobile stacks. URL state, debounce, pagination and clear-filter behavior retain the rating minimum.

Verify provider mapping, old/full/compact/unreported scores, stable sort/pagination, exact-title relevance, merged live matches, snapshot invalidation, malformed bounds, filter composition, previews and mobile fit. No content banks or model policies change; no bulk provider refresh is required.
