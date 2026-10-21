# 29. Read a movie from durable storage

## What changed

Catalog metadata can now be copied from our existing validated JSON snapshot into `data/private/movie-catalog.db`. It contains the same 1,500 movies. The live movie-detail endpoint now calls the learner-written lookup. Discovery continues to use its published vector snapshot. Search vectors, Chroma evidence and published facts/quizzes are untouched.

SQLite is a database stored in a file. You do not start a separate database server. Closing Python or restarting the backend does not erase its rows. Our in-memory dictionary caches disappear when their owning process stops.

## The table

```sql
CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
```

`movie_id` is the stable TMDB ID, not the title: different movies can share a title. A primary key also prevents duplicate rows and provides efficient ID lookup. `payload` contains one Movie object encoded as JSON, including title, cast, synopsis and poster URL. `fetched_at` records the metadata observation time; importing an old snapshot does not make it freshly fetched. This first schema keeps typed JSON for simplicity; later person/credit searches may need normalized tables or indexed columns.

The assistant implemented table creation, transactions, version checking, validated imports, idempotent writes and preservation of richer fields when incoming fields are absent. Batch failures roll back. A metadata database update does not automatically update semantic vectors.

## Your task

Open `backend/src/movie_companion/catalog_store.py`, find `CatalogStore.get_movie`, and replace its NotImplementedError with the five steps in its comments. Work only inside its existing database connection.

You already receive:

- `movie_id`: the validated positive ID requested by the caller.
- `db`: a SQLite connection whose rows support column names.
- `Movie`: the Pydantic response type.

A similar lookup in a different application:

```python
row = db.execute(
    "SELECT title FROM books WHERE book_id = ?",
    (book_id,),
).fetchone()
if row is None:
    return None
return row["title"]
```

The `?` is filled using the separate parameter tuple. Do not interpolate the ID into the SQL string. `(book_id,)` is a one-element tuple; `(book_id)` is just the value in parentheses. `fetchone()` returns one row, or None when no row matched.

Your movie lookup returns a Movie, not a JSON string. `Movie.model_validate_json(row["payload"])` parses the stored JSON and checks its field types. Compare the parsed movie ID with the requested ID before returning it so mismatched stored records cannot masquerade as another movie.

## Run it

From the project root, after completing the method:

```sh
backend/.venv/bin/python backend/scripts/try_catalog_store.py
```

Expected first line: `Interstellar 2014 Christopher Nolan`.
The final line confirms existing-film lookup, a missing-film lookup returning None, and persistence through a new CatalogStore instance. The learner completed the lookup and the assistant added lookup/fallback checks and API integration.

## How this will connect to the UI

The current path is movie tile → frontend getMovie → GET /api/movies/{id} → CatalogStore.get_movie → validated Movie JSON → frontend Movie page. For a missing/stale record, the backend will fetch TMDB metadata and save it. Returning stored metadata does not trigger quiz/facts preparation or an LLM call.

## Questions to revisit

Why use TMDB ID instead of title? IDs distinguish same-name films.
Why parse JSON into Movie? SQL returns stored text; the API requires validated structured fields.
What persists across a restart? SQLite rows; in-memory caches do not.
Why can metadata exist without a vector? Saving a provider result is cheap; model embedding is separate, versioned preparation.
Why return None? Missing data is a normal condition that lets the caller choose a provider fallback or an unavailable response.

## Review and live integration

Your implementation correctly uses a parameterised query, fetchone(), None for missing records, Pydantic JSON parsing and a canonical-ID comparison. The assistant added validation of the stored provider identity, seven-day freshness checks and the separate movie_details.py coordinator.

A fresh SQLite movie is returned without TMDB or Ollama. For missing/stale data, TMDB is called and validated metadata is saved. Failed refreshes return the last good saved movie without marking it fresh. A missing movie with no usable provider produces a recoverable 503; a provider 404 for a movie with no saved record remains 404. Invalid stored data fails with a sanitized error.

SQLite operations run through asyncio.to_thread so they do not block FastAPI's event loop. This is different from making a database call asynchronous: the synchronous SQLite work runs on a worker thread, while the async request waits for it. Source preparation, quizzes and embeddings are not triggered by this detail lookup.

Preparation now writes validated metadata separately before index publication; a metadata-only preparation can populate SQLite without model calls. This is not a single transaction spanning SQLite and JSON: valid metadata may be available before the next semantic index.

Verification: 383 backend tests passed; live Interstellar/Arrival responses matched their SQLite records (approximately 15ms and 2ms in a two-request local smoke check). These are observations, not load-test guarantees. Title/actor/director external search remains the next delivery.
