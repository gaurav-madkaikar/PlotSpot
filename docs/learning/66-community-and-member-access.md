# 66. Community discussions and member access

PlotSpot now has two kinds of conversation in **Discuss**: member-written threads and replies, followed by the existing source-backed AI question panel. Community posts are opinions, stored in the account database. They never enter the evidence database, vector index, facts bank or quiz bank.

## Follow one post from UI to storage

1. `movie.tsx` mounts `MemberFeatureGate` for Facts, Quiz and Discuss. Guests get a sign-in link that retains a validated movie/section destination. Member panels are not mounted for guests, so they do not request private content or invoke the model.
2. `movie-community-panel.tsx` reads movie threads, opens an inline form and sends your explicit submission. `community-post-form.tsx` collects bounded plain text and a spoiler label. `community-api.ts` includes the session cookie and CSRF token; Zod validates the response and checks its viewer identity.
3. `community_routes.py` checks the authenticated session and Origin/CSRF before writes. The author comes from the cookie, never submitted JSON. A posting allowance is checked before any movie-provider validation, limiting outbound work as well as writes.
4. `community_contracts.py` rejects unexpected fields, unreadable or oversized text, invalid identifiers and loose boolean values. A UUID submission key is accepted from JSON and validated as a UUID.
5. `community_store.py` commits the post to SQLite. The movie ID scopes threads; replies must belong to the same thread. Parent chains stop at three nested levels. Twenty threads or thirty replies are returned per page.
6. The UI refreshes the affected conversation and renders the body as React text. A string containing HTML stays text, never executable markup.

## What prevents accidental overwrites and duplicates?

Every editable post has a **revision**. An edit/delete must name the current revision, or the server returns 409. This is compare-and-swap: another tab's newer edit cannot be silently overwritten.

Creates carry a **submission key** and a hash of their original input. Retrying the same submission returns its original ID. Reusing a key with different content is rejected. The UI retains the key across an unchanged failed submission and starts a new key for a changed draft. This reduces duplicates when a response is lost; it does not automatically retry a write.

## Why protect access twice?

The UI gate helps navigation; the API gate enforces the rule. Someone can call an endpoint without clicking the page. Facts, quizzes, feature inventory, AI questions/expansion, preparation and community endpoints require sign-in at the server. Guest discovery, movie metadata, trailers, watch options, related films and temporary saves remain available.

Writes that generate content or change community data additionally need the existing CSRF/Origin check. Member responses, including errors, use `Cache-Control: no-store` and `Vary: Cookie`. Community query keys include account identity and spoiler permission; unused caches are removed. Account changes unmount the previous member panels and drafts.

## How are spoilers handled?

A labelled thread's title/body and a labelled reply's body are redacted by the API until spoilers are allowed. A thread or ancestor label also protects replies, even when a child has its own label disabled. Deleted or moderator-hidden replies become content-free placeholders so the conversation can retain its structure.

Turning spoilers off remounts the private panels and clears displayed answers/posts immediately. The switch shows its pending choice while the account preference is saved; a failed save returns it to the confirmed preference. A user can still forget to label a spoiler: reporting and moderator review address that case, rather than claiming automatic spoiler detection.

## How does moderation work?

A member can report someone else's visible thread/reply for spam, harassment, unlabelled spoilers or another reason. Reports do not automatically hide posts. Repeating a report for the same post revision returns the same report.

Only operator-configured moderator IDs can read the report queue or review it. Moderators can dismiss a report, hide a post or restore a moderator-hidden post from Reviewed. Owner-deleted posts cannot be restored. Actions check the current post revision and leave an audit row. Report text and spoiler content stay redacted until the reviewer enables spoilers.

For local setup, sign in to the moderator account and read only its `user.id` from `/api/auth/session` (the browser Network response, or `fetch('/api/auth/session').then(r => r.json()).then(s => console.log(s.user.id))`). Add that 32-character ID to `PLOTSPOT_MODERATOR_IDS` in the backend's ignored `.env`; use commas for multiple IDs and restart the API. The setting defaults to no moderators. Never grant roles through registration or client JSON. Real email delivery remains separately configured; local preview is development-only.

## Verification and practical limits

The backend suite covers membership before content/model I/O, CSRF/Origin, owner isolation, strict input, spoiler inheritance, duplicate keys, revisions, nesting, pagination, throttling, persistence and hide/restore audit history. Browser checks exercise real disposable accounts for sign-in, posting/replies, edit/delete/report, safe text, session changes and desktop/mobile layouts. The moderator UI browser fixture uses mocked report responses; actual role enforcement and moderation transactions are checked separately through the API.

These are deterministic application checks, not an AI safety accuracy score. Community is a local SQLite implementation with manual moderation. Production still needs operator staffing/policies, monitoring, abuse controls beyond this per-account limit, recovery/identity improvements and multi-user load qualification.

## Questions and answers

**Why aren't comments used as RAG evidence?** They may contain guesses, false claims or malicious instructions. Keeping them in a separate database prevents a user's opinion from being presented as a verified fact.

**Why not hide every reported post immediately?** A false report should not let one user censor another. Moderators decide using the current post and report details.

**Why not let the UI supply the author?** A modified browser request could impersonate someone. The session identifies the author, and the server checks ownership on every edit/delete.

**Are facts and quizzes generated once for each account?** No. Their verified saved banks remain shared by movie. Registration controls access; it does not duplicate content per user or change the generation pipeline.
