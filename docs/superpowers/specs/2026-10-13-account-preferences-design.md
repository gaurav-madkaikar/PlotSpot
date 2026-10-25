# Account preferences

Add two editable account preferences: allow spoilers by default (false) and include adult films in discovery (true, preserving current behavior). Store owner-scoped settings separately from collections with atomic revision checks; authenticated writes require existing Origin/CSRF protections. A missing row means defaults. Reset stages defaults in the form and Save persists them. No personal data goes to AI.

Return preferences with authenticated session data and update through PUT /api/me/preferences, returning the refreshed session. Failures retain edited fields; conflicts reload the account state for deliberate retry. Other tabs revalidate through the existing auth broadcast. Strict booleans and bounded revision reject coercion/extra fields.

Use two labelled switches in a warm paper preferences panel next to the collection summary, spanning the existing left-aligned page width; stack on mobile. Save/loading/error/status feedback uses existing tokens. Default spoiler consent combines with existing saved movie opt-ins. The movie switch overrides the global default for the current visit; existing per-movie opt-ins remain saved. Never reveal member content while auth is checking/failed or to guests.

Include-adult filters known TMDB adult=true records before local/live ranking and pagination, including suggestion movie IDs. Unknown classification remains eligible: this is a discovery preference, not age certification or a guarantee of suitability. Explicit adult-film URLs and saved collections remain accessible. Shared source metadata stays unchanged. Include effective adult mode in frozen search and browser-cache identities; backend intersects request mode with account setting. Filter title candidates before hydration. Legacy discovery surfaces also omit flagged movies but primary unified endpoint is the paginated user flow.

Validate persistence, isolation, revision conflicts, auth/CSRF, no-store, strict contracts, both adult modes/local-live caches, global spoilers/movie override, failure recovery, reload and responsive UI. Use only disposable accounts for browser verification.
