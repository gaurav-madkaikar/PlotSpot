# Named movie collections

The default collection, **All saved**, contains every movie the user saves. A saved movie may also belong to zero, one or several custom named collections. This extends the browser-local collection already in Frame; account synchronization is outside this change.

## Behavior

- Save from a movie tile or detail page adds the movie to All saved immediately and opens a collection picker. Closing the picker leaves that default save intact.
- The picker displays All saved as checked and fixed, custom collections as optional checkboxes, an inline collection creation form, and a Done action to apply custom memberships. Reopening a saved movie manages those memberships.
- Removing custom membership never removes the default save. A separate Remove from saved action removes the movie from All saved and every custom collection. Spoiler preferences remain independent.
- My collection provides All saved and custom collection views, counts, creation, rename and deletion. Deleting a custom collection preserves its movies in All saved.
- Collection names are trimmed, collapse whitespace, and have 1–60 characters. Case-insensitive duplicate names and the reserved All saved name are rejected inline.
- Existing browser data and watched preferences are preserved. Collections synchronize across open tabs and persist across reloads using the existing validated storage envelope; old data without custom collections loads as an empty custom collection list.

## Boundaries and UI

The collection provider owns storage and membership invariants. A shared save control serves tiles and the movie hero. A native modal dialog supplies focus containment, Escape dismissal and focus restoration. The collection page selects a view using its URL. Use existing cream surfaces, red accent, editorial headings, rounded controls and concise copy. No dependencies or backend/user accounts are introduced.

## Validation

Browser journeys cover legacy storage, multi-collection membership, persistence, duplicate/empty names, custom-only removal, global removal, rename/delete preservation, unavailable movies, keyboard focus, Escape and narrow layouts. Existing collection, TMDB and movie overview checks must pass, along with the frontend build.
