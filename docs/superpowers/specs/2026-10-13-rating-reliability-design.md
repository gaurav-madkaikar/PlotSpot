# Vote-aware discovery order

The user approved improving rating reliability. Choose a smooth vote-weighted order rather than excluding newer films with a hard vote cutoff. Preserve displayed TMDB averages, raw minimum-rating eligibility, exact-title/person-credit relevance and all other filters.

Best rated is the default: adjusted = 7 + (reported_average - 7) * votes / (votes + 500). The fixed 7/10 reference and 500-vote weight are transparent versioned application policy, not an observed TMDB global mean or a calibrated confidence interval. No catalog-derived per-query baseline, synthetic displayed rating, popularity signal, model inference, source refresh or data migration.

Highest score remains selectable for raw average descending. Both use reported score, vote count, title and ID for deterministic ties; missing/zero-vote records remain last. Sort the full matching pool before pagination; preserve identity tiers and canonical-prefix precedence. Include sort mode and policy version in unified snapshot identity. Existing saved previews/related tiles retain their source order; all preview badges show the true score and compact vote count.

Place a small labelled Sort by control on the results row using existing rounded tokens, with Best rated / Highest score choices and accessible explanatory text. Keep search/four-filter toolbar unchanged. URL sorting persists through typing, suggestions, filters and pagination; changing it resets page/token. Clear filters preserves the chosen sort. Explicit default sort in request parameters prevents reuse of old raw-order frontend query caches.

Verify two-vote 10 below a well-supported 8.5, rising support for genuinely high-score new films, mathematical bounds, authoritative full/compact values, raw-score eligibility, unreported states, exact matching, actor/merged-live pools, stable pages and sort-token reset. Validate keyboard controls, visible vote counts, mode switching, clear/typing behavior and desktop/mobile fit. Compare both modes on identical current local records without network or content writes. These checks demonstrate deterministic policy behavior, not recommendation quality.
