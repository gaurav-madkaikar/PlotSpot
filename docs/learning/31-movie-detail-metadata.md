# 31. Rich movie metadata and character credits

## From TMDB to the overview

TMDB's `/movie/{id}` response already contains release date, spoken languages, production companies/countries, budget, revenue, status, original title, `vote_average` and `vote_count`. Our existing `append_to_response=credits` includes the cast records, with each actor's `character` and `profile_path`. No LLM or extra per-actor request is needed.

`movie_metadata.py` translates these optional fields into `MovieMetadata`. It keeps up to twelve cast credits and only constructs portrait URLs from validated TMDB image paths. `TmdbClient.movie` attaches this as `Movie.detail_metadata`; existing `cast: list[str]` remains available for name search and older consumers.

The FastAPI movie route returns the Movie object. Zod validates the added optional object in `frontend/src/lib/contracts.ts`. `MovieDetails` formats dates, USD financial values and production tags; `MovieCast` renders portrait/role cards. The movie header displays the rating and vote count. A missing or failed portrait shows initials. Missing cast roles are labelled “Role not listed.”

## Why use an optional nested object?

Existing SQLite records and demo fixtures contain only the old metadata. `detail_metadata=None` distinguishes those old records from a freshly read movie whose budget or cast roles genuinely aren't reported. Its version field lets us identify the normalized detail format.

When a saved movie has no detail_metadata and the provider is available, opening it refreshes the metadata even if the old basic record is less than seven days old. Successful enrichment persists in SQLite. Later reads reuse the saved result. Provider failure still serves the old movie; a missing credential also permits saved reads.

Optional missing fields in a later refresh preserve richer saved metadata. The existing semantic snapshot remains unchanged: new optional defaults are excluded from old fingerprints, while populated detail metadata participates in newly generated fingerprints. This prevents a schema addition from invalidating the existing 1,500 vectors.

## Accurate labels

- `vote_average` is a TMDB user rating out of ten, accompanied by `vote_count`. It isn't an IMDb or Rotten Tomatoes score.
- `spoken_languages` describes languages spoken in the film. It doesn't guarantee which dubbed or subtitled editions are available in each country.
- `release_date` is TMDB's top-level release date; region-specific release dates are a separate endpoint.
- Budget/revenue are shown in USD. TMDB's zero values are treated as unreported, not a zero-cost production or zero box office.
- Movie status and production countries provide additional context when present.

## Questions and answers

**Why keep the old cast list?** It is used by search and existing metadata records. Structured credits add role/portrait information without breaking those callers.

**Why not ask an LLM for character names?** The credits API supplies them directly; an LLM could invent a role.

**Why fetch these fields on a detail-page visit rather than enrich every saved movie now?** It avoids thousands of unnecessary calls while making the selected movie complete. The result is saved for reuse.

**Why is null different from zero?** Null means unknown or unreported. A rating of zero with votes is a numeric value; a financial zero in this provider's metadata generally indicates no reported figure.

**Why validate portrait paths?** A provider field must not become an arbitrary remote image URL. Images are restricted to TMDB's image host and expected path format.

References: [movie details](https://developer.themoviedb.org/reference/movie-details), [movie credits](https://developer.themoviedb.org/reference/movie-credits).
