# Named collections: one film, several shelves

A movie can appear in more than one collection. For example, Arrival can be in both **Weekend favourites** and **Science fiction**. Both collections point to movie ID `329865`; neither copies the movie metadata.

## The stored shape

The existing browser-local key, `frame.demo.collection.v1`, now contains:

```json
{
  "saved": [329865, 438631],
  "watched": [329865],
  "collections": [
    { "id": "a-stable-collection-id", "name": "Weekend favourites", "movieIds": [329865] },
    { "id": "another-stable-id", "name": "Science fiction", "movieIds": [329865, 438631] }
  ]
}
```

**All saved** is the `saved` array. It is derived rather than duplicated as a custom collection. That means there is only one authoritative list of saved movies. Every custom collection's movie IDs must be a subset of that list. The watched array remains independent so unsaving a film does not reset its spoiler preference.

Zod gives `collections` a default of `[]`. Existing saves containing only `saved` and `watched` remain valid. Reading storage also removes duplicate IDs and orphan custom memberships. Corrupt storage shows a warning; it is not silently overwritten on startup. A later deliberate change attempts recovery.

## How the UI connects

1. `SaveMovieControl` is shared by tiles and the movie hero. Saving adds a movie to All saved immediately, then opens the picker.
2. The picker holds a temporary selection of custom collection IDs. Done applies those selections through `setMovieCollections`. Closing with Escape keeps the default save but discards unsubmitted membership edits. A collection created in the picker persists even if the membership edits are dismissed.
3. `CollectionProvider` updates React state with a functional setter. All consumers immediately receive the new state. Its persistence effect writes JSON to browser storage and shows a warning if saving fails.
4. The collection page reads the selected collection ID from its URL and requests movie details for those IDs through the existing API client and query cache.
5. Browser `storage` events refresh other open tabs. Equal serialized state is not written again, avoiding a loop of repeated updates. Invalid changes from another tab show a warning while retaining the current valid state.

Collection IDs remain stable when names change. Names are trimmed, repeated whitespace is collapsed, and case-insensitive duplicates, empty names and the reserved All saved name are rejected. Deleting a custom collection removes only its grouping. Remove from saved removes the movie ID from the default list and every custom collection.

## Why use a context and native dialog?

React context shares the collection state across otherwise unrelated pages and cards. It prevents separate save buttons from maintaining contradictory copies of the same list. Native `dialog.showModal()` supplies modal semantics, focus containment and Escape handling. We also restore focus explicitly when Done unmounts the picker; browser checks caught that missing behavior during implementation.

## What would change with accounts?

These collections currently live in this browser, not the backend database. A future authenticated implementation would usually use `collections`, `saved_movies` and `collection_movies` tables, with a unique `(collection_id, movie_id)` membership and ownership checks on every write. Local storage currently follows last-write-wins behavior across tabs; it is not a database transaction or multi-device synchronization.

The important relationship is many-to-many: a collection holds many movies and a movie belongs to many custom collections. The default saved list remains the complete set of the user's saved movies.
