# 69. Account preferences

PlotSpot now stores two explicit choices: **Allow spoilers by default** and **Include adult films in discovery**. These are account data, not instructions for a model. No LLM call is needed to read, save or apply them.

## How a save travels through the app

1. The authenticated session carries `user.preferences`. A new or existing account with no settings row receives spoilers off and adult inclusion on.
2. `AccountPreferencesPanel` copies those settings into a draft. Changing a switch updates only React state. Save submits the complete draft; Reset stages the default values and still requires Save.
3. `AuthProvider.updatePreferences` calls the private API with the existing CSRF token. Zod checks the response and verifies that the returned account is the expected owner.
4. The backend derives ownership from the session cookie, checks Origin and CSRF, validates actual boolean values and writes `account_preferences` in the private account SQLite database. Settings do not change the collections table/revision.
5. The refreshed session updates React and broadcasts a revalidation signal to other tabs. Responses use `no-store`; private settings never go in localStorage or an AI prompt.

Relevant files: `frontend/src/components/account-preferences-panel.tsx`, `frontend/src/lib/auth.tsx`, `frontend/src/lib/account-api.ts`, `backend/src/movie_companion/account_preferences.py`, `backend/src/movie_companion/account_routes.py` and `backend/src/movie_companion/accounts.py`.

## Why keep a revision number?

Suppose two tabs read revision 4. The first saves and the server advances to 5. The second submits 4: the server returns 409 instead of overwriting the first tab's changes. The editor retains its draft, refreshes account state and asks the viewer to load the latest preferences before trying again. A failed network save also retains edits; it never claims they were saved.

Updates run in a SQLite transaction with a write lock, so checking the revision and updating the row are one atomic operation. The server rejects a forged owner field, missing fields, strings such as `"false"`, numeric booleans and invalid revisions.

## Where adult-film filtering happens

The discovery request includes `include_adult=false` when the account excludes adult films. The backend also reads the session setting and intersects the request with it: a client cannot re-enable adult inclusion by editing the query string while the saved setting is off.

A filtered prepared catalog supplies both keyword retrieval and spelling suggestions. Flagged movies are removed before ranking and pagination; filtering only the visible page would give incorrect totals and gaps. Live title candidates already marked adult are skipped before hydration. Hydrated results are filtered before entering the final merged pool. Shared metadata remains unchanged.

Server snapshot identities include adult mode. Browser result cache keys include the owner and adult mode, preventing a cached adult-inclusive result from being reused for an account that excludes adult films. Discovery pauses while initial account identity is being checked.

This uses TMDB's `adult` flag, which is not an age certificate. Unknown classifications remain eligible, and ordinary films may contain mature themes. Explicit movie URLs and saved collections remain accessible. This is a discovery preference, not an access restriction.

## How spoiler defaults interact with movie controls

The account setting grants default spoiler consent for member features. Existing saved per-movie opt-ins are retained. The movie toggle can turn spoilers off for the current visit even when the account default is on. Switching that movie control does not rewrite the global preference. Turning the global default off does not erase previous movie-specific opt-ins.

Guests still cannot access Facts, Quiz or Discuss. Content is not revealed while account access is being checked or has failed. Shared facts and quiz banks remain movie-scoped and unchanged.

## Checks and learning questions

- **Are preferences part of RAG memory?** No. They are explicit, editable user settings applied deterministically. Storing opinions or private notes for later retrieval would be a different feature.
- **Why not save each switch immediately?** A draft and Save action let viewers review choices and make failures/conflicts clear. It also avoids overlapping requests when switches change quickly.
- **Why use separate revisions?** A preference save should not conflict with adding a film to a collection. Each independently editable resource has its own revision.
- **Why filter before pagination?** Otherwise a 20-film page could shrink after filtering, while totals and page counts still include hidden films.
- **Why validate on both sides?** Backend validation protects stored data; frontend validation prevents unexpected responses from becoming UI state. Neither replaces session ownership or CSRF checks.

Validation: 1,268 backend checks; 40 affected browser checks; TypeScript/production build; native inspection of the running account page. Browser checks used disposable accounts, including persistence, isolation, save failures, conflicts, reset, spoiler overrides, cache-mode changes and layouts at 1440, 768 and 375 pixels. All 11 shared movie content banks retain their previous publication hashes.
