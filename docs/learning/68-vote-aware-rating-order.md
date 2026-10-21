# 68. Vote-aware movie ranking

Discovery now defaults to **Best rated**, which balances a movie's average score with the number of votes. **Highest score** retains the original raw-score order. Cards show the real TMDB average and compact vote count in either mode. Switching order never changes a movie's stored rating.

## Why a perfect score might come later

Two people giving a film 10/10 is a much smaller sample than ten thousand people giving another film 8.5/10. Sorting by raw averages alone previously put the two-vote film first.

The new order uses a fixed reference score and gradually gives the movie's own average more weight as its vote count grows:

```text
ordering_score = 7 + (movie_average - 7) × votes / (votes + 500)
```

- A 10.0 from 2 votes gets an ordering score of about 7.012.
- An 8.5 from 10,000 votes gets an ordering score of about 8.429.
- At 500 votes, the ordering score is halfway between the reference and the movie's average.
- A newer 9.0-rated film can rise as it receives more votes; it is not excluded by a hard threshold.

The ordering score is internal. Users continue to see **10.0** and **8.5** on those cards, alongside the vote counts.

## What do 7 and 500 mean?

They are explicit application policy, versioned as `trusted-rating-v1-reference-7-weight-500` in `movie_ratings.py`. The 7 is not a claimed TMDB global mean. The 500 is the strength of the reference, not a minimum number of votes or a confidence percentage. This is Bayesian-style shrinkage, not a calibrated confidence interval, proof of film quality or a measured recommendation-accuracy score.

Using fixed values avoids a surprising change when a user selects a genre or goes to another page. Estimating a baseline from the current page would let the same film receive a different ordering score merely because the page changed. Future policy changes should be independently assessed and get a new policy version.

## How the pieces connect

1. `movie_ratings.py` reads authoritative full metadata or the compact preview fields, calculates the internal value and builds the chosen sort key. Unreported/zero-vote records stay last. Original average, count and stable title/ID ordering break ties.
2. `CatalogQuery.sort_by` and the public local/catalog API accept only `trusted` or `rating`. Search continues to prioritize exact identities and canonical title completions, then applies the chosen rating order within comparable matches.
3. `catalog_search.py` sorts the entire matching pool before slicing pages. `unified_discovery.py` uses the same order after merging verified live matches. Its snapshot identity includes both mode and policy version; a changed mode cannot reuse an old frozen page.
4. `movie-search.tsx` provides the results-row Sort by control. Sort survives typing, suggestions, filters, pagination and Clear filters; changing it resets the page/token. Requests explicitly include the default, so the frontend cannot reuse the earlier raw-order query cache.
5. `MovieRatingBadge` displays the original score with TMDB attribution and a compact vote count. Its accessible label/hover title retain the full count. Collection and related-film previews share the badge; their membership/source order is unchanged.

## Why can 9+ still show unfamiliar films?

The minimum-rating filter still means **original TMDB average**, not the internal ordering score. A popular film rated 8.5 does not qualify for 9+. Switching to Any rating or 8+ includes it. We did not silently add a vote cutoff or lower the selected minimum.

## Verification

Synthetic checks cover a two-vote perfect score, growing support for a new film, bounded/finite calculations, missing votes, exact identities, actor matches, whole-pool pagination, raw eligibility, API mode validation, local previews and frozen-token resets after a mode/policy change. Browser checks cover the selector, visible votes, mode switching, page reset, typing/clearing and desktop/mobile layouts.

A read-only comparison uses the same current 2,850 local movie records for both modes; 704 have reported ratings. Best rated begins with 12 Angry Men, Spirited Away, The Dark Knight, Interstellar and Inception in that snapshot. Raw order still begins with sparse perfect scores. The same-input hash and both top lists are retained in `.cache/trusted-rating-comparison.json`. This verifies the intended behavior on this local corpus, not globally complete coverage or independently evaluated recommendation quality. No provider/model calls or content-bank publications were needed for the comparison.
