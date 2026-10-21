# 34. Watch options and related movies

## What we added

The movie page now shows watch availability for a selected country and six related movie tiles. These are read-only TMDB features: no Ollama call, evidence ingestion or quiz generation is needed.

Watch data comes from TMDB's [movie watch providers endpoint](https://developer.themoviedb.org/reference/movie-watch-providers). Its availability data requires JustWatch attribution. We show the provided TMDB watch-page link rather than inventing links to a provider's player or prices. Recommendations come from [movie recommendations](https://developer.themoviedb.org/reference/movie-recommendations); the country list comes from [available regions](https://developer.themoviedb.org/reference/watch-providers-available-regions).

## Follow one request

1. As the watch section approaches the viewport, `movie-watch-options.tsx` requests `/api/movies/27205/watch?country=IN` through `api.ts`.
2. `main.py` asks `load_extra` in `movie_extras_store.py` for the key `watch:27205:IN`.
3. A fresh SQLite response is returned immediately. Otherwise, `tmdb_client.py` fetches `/movie/27205/watch/providers`.
4. `movie_extras.py` selects only the `IN` entry from TMDB's country map, validates IDs and URLs, removes duplicates, and translates `flatrate` into our `subscription` category.
5. The successful normalized response is saved with its check time. Frontend Zod validation checks the response before the component renders it.

The API response is a small contract rather than the entire TMDB payload:

```json
{
  "movie_id": 27205,
  "country": "IN",
  "status": "available",
  "groups": [
    {"kind": "subscription", "providers": [
      {"id": 119, "name": "Amazon Prime Video", "logo_url": null}
    ]}
  ],
  "watch_url": "https://www.themoviedb.org/movie/27205-inception/watch?locale=IN",
  "checked_at": "2026-10-11T10:00:00+00:00",
  "stale": false
}
```

This is an illustrative shape; providers and availability change. An empty result means TMDB lists no options for that country, not that watching the film is impossible.

## Three cache layers

| Layer | Stored information | Freshness |
| --- | --- | --- |
| Frontend TanStack Query | Validated endpoint responses, keyed by movie and country | Watch 10 minutes; related 1 hour; regions 1 day |
| Backend SQLite extras cache | Normalized responses and original successful check time | Watch 6 hours; related 1 day; regions 7 days |
| TMDB client memory cache | Raw responses for repeated provider requests | 10 minutes; bounded to 256 entries |

SQLite survives restarts; the in-memory caches do not. Extras live separately from the saved movie catalog and its semantic embeddings. Updating availability does not require rebuilding movie vectors. SQLite retains at most 2,000 extras entries.

If refresh fails, we may show a previously successful response, clearly labelled stale. Its maximum total age is three days for watch options, seven days for related films and thirty days for regions. Failures are never saved as successful responses. Each provider operation has a twelve-second overall deadline.

## Concepts and answers

**Why include the country in both cache keys?** India and the United States may have different services. A key containing only the movie ID could serve the wrong country's response.

**What happens if the user changes country quickly?** Each country has its own query key, and the fetch receives an AbortSignal. An earlier India's response cannot replace the currently selected United States query. We also validate that the response matches the requested movie and country.

**Why keep these requests separate from movie details?** Availability or recommendations can fail while the overview, cast and trailer still work. Each optional section has its own retry and honest empty state.

**Why don't related tiles fetch every movie's full details?** TMDB recommendations already include title, year and poster. Using those summaries avoids six unnecessary detail requests. Selecting a tile fetches that movie's details, and the back link returns to the source film's related section.

**Are these AI recommendations?** No. This section uses TMDB recommendations. Our local story/mood search is a separate evaluated AI pipeline. Keeping this distinction makes the feature and its measurements easier to explain.

**Which guardrails apply here?** Strict movie/country identity checks, trusted image hosts, a validated TMDB watch link, response-size bounds, bounded caches and request deadlines. The backend makes fixed read-only provider calls; the model has no role in choosing these URLs. These checks reduce specific risks and do not prove universal safety.

**How did we verify it?** Offline tests cover cache expiry, persistence, country isolation, stale fallback, invalid links/identities, future timestamps, capacity and timeouts. Browser tests cover country-switch races, recoverable section errors, small-screen layout and related navigation. Live provider data is checked separately from deterministic test fixtures.
