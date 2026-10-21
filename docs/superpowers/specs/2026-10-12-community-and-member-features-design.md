# Community discussions and member-only movie features

The user explicitly approved community threads/replies, spoiler labels, owner editing/deletion, reporting and moderation, and requested that Facts, Quiz and Discuss be available only to registered users. Existing verified account sessions (and preserved legacy accounts) establish membership. UI follows the existing warm paper, ink, accent, page gutters and feature panels; consumer draft workspaces remain hidden.

## Member boundary

Movie metadata, discovery, trailers/watch/related movies and guest saves remain available. Facts, quiz, feature inventory, questions, quiz expansion and internal preparation endpoints require an authenticated account at the API boundary. JSON mutations that invoke inference, generation or community writes also require existing Origin/CSRF validation. Member responses use no-store and Vary Cookie. Guest sections show a concise sign-in/create-account card and do not fetch member data. Only approved local movie return paths with fixed section hashes may follow sign-in; no external redirects.

## Community

Use the existing private account SQLite database, with foreign keys and bounded transactions, separate tables from movie evidence/content. Movie-scoped threads have titles, plain-text bodies, author usernames, spoiler flags, timestamps and revisions. Replies support a parent from the same thread and at most three nesting levels. Lists paginate (20 threads, 30 replies). Thread creation validates movie identity against the demo/provider metadata path; posts never call an LLM. Request UUIDs make identical creation retries idempotent; different payload reuse fails.

Only authors edit/delete their posts. Revision checks reject stale edits. Thread deletion removes it from ordinary discovery; reply deletion leaves a text-free tombstone so children retain context. Spoiler-flagged thread titles/bodies and reply bodies are redacted by the server unless allow_spoilers is true; parent/thread spoiler labels propagate to replies. Switching spoilers off clears disclosed content before new reads finish.

Users can report threads/replies with bounded reasons/details. Reports never hide content automatically, avoiding brigading. Moderators are assigned only by server-side account UUID allowlist (PLOTSPOT_MODERATOR_IDS), not registration or client fields. A moderator report queue supports dismiss/hide/restore decisions with audit records and revision checks. Report excerpts respect spoiler consent. There is no automatic AI moderation claim. User content is untrusted opinion and never enters factual RAG or facts/quiz generation.

## UI and tests

Discuss contains a community panel followed by the existing evidence-grounded AI panel. Inline thread views, reply forms, plain text rendering, labelled spoiler switches, icon-only edit/remove/report actions with accessible names, delete confirmation dialogs, loading/error/retry, pagination, and mobile wrapping use existing components/tokens. Backend checks cover membership, CSRF, owner spoofing, movie scope, nesting, spoilers, idempotency, stale writes, reporting/roles and moderation. Browser checks cover guest gates/no member calls, signed-in content, posting/replies/edit/delete/report and responsive layouts using disposable databases. Preserve shared movie banks and existing RAG policies.
