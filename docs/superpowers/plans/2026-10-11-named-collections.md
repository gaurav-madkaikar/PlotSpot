# Named Collections Implementation Plan

> Execute inline with executing-plans; the user has asked the assistant to perform implementation and checks.

**Goal:** Let users organize saved movies into multiple named collections while All saved always contains every saved movie.

**Architecture:** Extend the existing browser-local provider. Share the save picker across discovery and detail pages; let the collection page select a named view by URL.

**Tech Stack:** React, TypeScript, Zod, React Router, native dialog, existing Playwright checks.

## Global constraints

- Preserve legacy `frame.demo.collection.v1` saves and watched preferences.
- Custom membership is always a subset of saved movie IDs.
- Deleting a custom collection does not unsave its movies.
- Validate 1–60 character names, duplicates and reserved All saved name.
- Keep existing visual tokens, keyboard accessibility and responsive layouts.
- No backend changes, new packages, account wiring or unrelated refactoring.

## Tasks

- [x] Add `frontend/e2e/named-collections.spec.ts` journeys for a movie in two collections, default membership, reload persistence, custom removal, global removal, name validation, rename/delete, legacy migration, keyboard and mobile behavior.
- [x] Extend `frontend/src/lib/collection.tsx` with `collections: {id:string; name:string; movieIds:number[]}[]`, `saveMovie(id)`, `removeSaved(id)`, `setMovieCollections(id, collectionIds)`, `createCollection(name)`, `renameCollection(id,name)` and `deleteCollection(id)`. Parse old storage with collections defaulting to `[]`; sanitize duplicate/orphan memberships. Return explicit inline name errors from create/rename.
- [x] Add `frontend/src/components/collection-dialog.tsx` for native modal behavior, `collection-name-form.tsx` for validated creation/rename, and `save-movie-control.tsx` for saving and membership selection. Connect the shared control to `movie-card.tsx` and `pages/movie.tsx`.
- [x] Update `frontend/src/pages/collection.tsx` with URL-selected collection views, creation, rename/deletion controls, counts, relevant empty states and unavailable movie removal. Preserve API detail fetching and retry behavior.
- [x] Add styles in `frontend/src/styles.css` using semantic tokens and narrow-screen wrapping. Update prior tests that assumed saved controls immediately unsave; save now opens a picker.
- [x] Build and run named collection, foundation, TMDB and movie overview browser journeys on isolated demo servers. Inspect the live UI in a temporary browser context and capture a screenshot. Document storage behavior for later learning.
