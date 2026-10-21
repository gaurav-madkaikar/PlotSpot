# 67. Movie ratings, filters and ordering

Discovery now offers a **Minimum rating** filter: Any rating, 6+, 7+, 8+ or 9+. TMDB scores appear on discovery, collection and related-film previews. Browsing lists higher-rated films first; exact title and comparable search-relevance groups still determine which matches belong ahead of incidental description matches.

## Data and display

TMDB exposes `vote_average` (0–10) and `vote_count`. Full catalog records already store them in `detail_metadata`. Lightweight search/title/recommendation records now carry the same two optional fields without requiring full credits, finances or an individual movie-details call for each search tile.

`movie_ratings.py` reads full metadata when present, otherwise compact fields. A score needs a positive vote count; zero votes means unrated. Missing fields mean rating unavailable. Frontend `movie-ratings.ts` follows the same rule, and `MovieRatingBadge` supplies the shared star, rounded score, attribution and accessible vote-count label. Provider values are bounded and validated; no AI inference or invented demo ratings are involved.

Older SQLite payloads remain readable without migration. Some old previews have no vote fields: title discovery can refresh them from an available validated TMDB candidate. They stay unavailable until reliable metadata arrives. Complete existing movie details remain authoritative and are not overwritten by a lightweight preview. Related-film caches retain their normal expiry behavior.

## Follow the filter

1. `movie-search.tsx` stores the selected value as `min_rating` in the URL. Selecting it resets the page and frozen search token while preserving query, genre, runtime and language. Typing/suggestions preserve the threshold; Clear filters removes it.
2. The API client sends that parameter to `/api/search/catalog` and its progressive `/api/search/local` companion. FastAPI and `CatalogQuery` enforce finite values between 0 and 10.
3. `eligible()` applies it alongside the other filters. Unknown/unrated movies are excluded when a minimum is supplied.
4. The backend sorts the entire matching pool before slicing a page. Rating descends first inside comparable relevance groups; vote count breaks equal-score ties, then stable title/ID ordering. Browsing has no query-relevance groups, so ratings lead directly.
5. Unified discovery applies the same rules after merging local movies and verified live matches. Its snapshot identity includes the threshold, so an old token cannot reuse the previous filter's pool. Later pages use the same frozen ordered pool rather than being independently reordered.

## Why not sort the twenty displayed cards in the browser?

The highest-rated matching movie could be on page five. Sorting only page one cannot move it to the correct position or calculate the filtered result count. Filtering/ranking the whole pool before pagination makes the count and page membership agree. “Whole pool” still means the application's bounded local/live search results, not the entire worldwide TMDB catalog.

## Why keep title relevance?

Searching an exact movie title should return that movie before a higher-rated film whose description merely mentions the same words. Actor/director filmographies use verified credits for membership and ratings within those matches. Title-completion groups also retain their canonical-prefix preference, then use ratings before length/name tie-breaks.

## Why show the vote count?

A 9.0 from ten voters and a 9.0 from ten thousand voters have different evidence behind them. Counts appear in the badge's accessible label and hover title, and break equal-score ties. This version uses raw TMDB averages, not popularity or a Bayesian confidence-adjusted ranking.

## Verification

Tests cover compact/full/legacy metadata, strict provider bounds, missing/zero votes, rating order before pagination, combined filters, exact-title relevance, actor credits, frozen-token resets and rating refresh from title candidates. Browser checks verify displayed scores, clear/typing behavior, page reset, related tiles and layouts at 1440/900/375px. Application tests do not measure recommendation quality or represent live IMDb/Rotten Tomatoes ratings.
