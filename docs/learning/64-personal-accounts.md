# 64. Accounts, sessions and personal collections

You can now create a local username/password account from **Sign in**, then keep
saved films, named collections and spoiler/watched state in the backend database.
Guests retain their browser saves. Signing in never silently imports those saves;
**Import browser saves** is a deliberate action on the Account page.

Facts, quizzes, movie metadata and public evidence still belong to movies and are
shared. Account state belongs to its owner. None of these account APIs calls an
LLM or sends credentials, collections or session information to retrieval tools.

## Follow one sign-in

1. The React `AuthProvider` calls `GET /api/auth/session`. It returns a user or an
   anonymous session envelope plus a CSRF token. The browser stores an HTTP-only
   cookie; JavaScript keeps the CSRF value only in memory.
2. Submitting the form sends username/password JSON with `X-CSRF-Token`. The browser
   attaches its cookie. The backend checks the exact configured Origin and matches
   the token to the session before checking credentials.
3. `AccountStore.login` loads a password hash, verifies it with Argon2id, and creates
   a fresh random signed-in session. Its raw token is sent only as a cookie; its
   SHA-256 hash is stored in SQLite. The preceding anonymous session is revoked.
4. The response contains the account ID/username and new CSRF token. React remounts
   `CollectionProvider` for that owner and fetches `/api/me/collection`.
5. The backend derives the owner from the session, returns `{owner_id, snapshot}`,
   and the client verifies that owner before rendering the collection.

Start in `frontend/src/lib/auth.tsx` and `account-api.ts`, then
`backend/src/movie_companion/account_routes.py` and `accounts.py`. The account page
is `frontend/src/pages/account.tsx`; the root composition is in `main.tsx`.

## Password hashing is not encryption

A password hash is a one-way verification record. We verify a submitted password;
we do not decrypt a stored password. Argon2id uses a fresh salt and deliberately
expensive work. This implementation uses 19456 KiB memory, two iterations and one
parallel lane, matching the minimum Argon2id profile in the
[OWASP password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
The [argon2-cffi guide](https://argon2-cffi.readthedocs.io/en/stable/howto.html)
explains hashing, verification and rehashing when parameters change.

Passwords are 6–128 characters and are not silently trimmed or truncated. Usernames
are normalized and case-insensitively unique. Unknown usernames still perform a
verification against a dummy hash; wrong credentials return the same error. SQLite
attempt counters limit expensive login/register work per client and normalized
client/username pair. They survive a service restart. This is not a distributed
rate limiter or an assertion that timing differences are entirely eliminated.

Session tokens are different: they already contain 256 bits of randomness, so a
fast SHA-256 hash is suitable for storing their lookup identity. Passwords usually
have far less entropy and need a password-hashing function.

## Why two cookies?

The signed-in cookie is `frame_session`; the anonymous bootstrap cookie is
`frame_guest`. HTTPS mode uses the corresponding `__Host-` names. Both are
HTTP-only, SameSite=Strict and Path=/; HTTPS mode adds Secure.

An existing-session GET does not set cookies. Imagine a slow read started before
login but finished afterward. If that read rewrote the old signed-in cookie, it
could undo login. A delayed anonymous bootstrap can now write only the separate
guest cookie, which cannot replace the authenticated session. Resolution always
prioritizes a valid signed-in cookie. Login/register rotate tokens; logout revokes
the token and removes the signed-in cookie.

Signed-in sessions have a seven-day absolute lifetime and one-day idle lifetime;
anonymous sessions last ten minutes. Revocation and expiry are checked on the
server. No bearer token is stored in localStorage.

## Cookie and CSRF do different jobs

The cookie identifies the session. Because browsers attach cookies automatically,
unsafe requests also require a session-bound synchronizer token and the exact
allowed Origin. The CSRF token alone cannot identify a user or replace a cookie.
Malformed/non-ASCII tokens are rejected before constant-time comparison.
SameSite is another protection, not the only one. See the
[OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

Private API bodies must be JSON and fit within 128 KiB, including chunked requests.
Private responses use `Cache-Control: no-store`. Validation errors deliberately
omit submitted values: FastAPI's default detailed error could otherwise echo an
invalid password back to the browser. Password managers, autocomplete, paste and a
visible-password toggle are supported in the form.

## What is stored, and where?

The default private database is `backend/data/private/accounts/accounts.db`:

- `users`: account ID, display username, normalized username key and password hash.
- `sessions`: hashed session token, CSRF value, owner, absolute expiry and last use.
- `auth_limits`: hashed throttle keys, window start and attempt count.
- `personal_collections`: one owner-scoped, revisioned JSON snapshot of saved IDs,
  watched/spoiler IDs and named collections.

A snapshot is bounded to 2000 saved/watched IDs, 50 named collections and 4000
membership entries. Custom memberships must be unique and drawn from All saved.
Names are normalized, at most 60 characters and case-insensitively unique; All saved
is reserved. Private database permissions are restricted and databases are ignored
by Git. This is access-controlled plaintext personal state, not encrypted storage.

A bounded JSON snapshot keeps this learning implementation small. For much larger
libraries or query-heavy community features, separate relational membership tables
would be a reasonable next migration. This implementation does not duplicate full
movie metadata into each user's row.

## A save is an async round trip

Previously `createCollection` only changed React state/localStorage. It now returns
an awaited result. For signed-in users the form closes only after the server confirms
persistence. A busy guard prevents overlapping edits; failures keep the dialog and
old collection available. Guests retain their existing browser behaviour.

The server sends a revision. If your tab loaded revision 4, its next PUT must include
4. A successful save commits revision 5 in the same transaction. A second tab still
sending 4 receives 409 instead of overwriting the newer collection. The frontend
loads the newer state and leaves the rejected edit available for deliberate retry.
It does not silently replay an old replacement snapshot.

A delayed GET also cannot replace a newer local revision. Owner checks protect
identity, while revision checks protect ordering; both are needed.

Follow `personal_store.py` and `personal_contracts.py` on the backend, then
`collection.tsx` and the awaited `CollectionNameForm` / `SaveMovieControl` callers.

## Importing browser saves safely

The browser's old key remains `frame.demo.collection.v1`. Account data is never
written there. An explicit import merges saved/watched IDs, merges collections by
normalized name, creates new server IDs when needed, and validates the combined
limits under a revision check. Repeating an import does not duplicate memberships,
although a successful request still advances the revision.

The browser copy remains intact. Another account sees its own empty/server library
until its user explicitly chooses an import. Signing out restores guest browser
saves rather than copying the departing account's state into guest storage.

## Account changes and recovery

A BroadcastChannel announces only that the session changed; it carries no tokens
or collection data. Focus also revalidates identity. Loading/failed identity checks
hide personal state and disable edits. Responses from a different owner are rejected,
and the owner-keyed provider discards old account state on a switch.

Authentication errors refresh the session after releasing the mutation lock, then
leave the original action for the user to retry. Credentials are never automatically
resubmitted. Personal authorization errors have one automatic recovery per session;
persistent rejection stops on manual retry. React StrictMode can start an additional
initial read that gets cancelled; this is not an unbounded polling loop.

## Actual verification

- 1,146 backend checks pass, including 26 new account/store/HTTP checks.
- 22 affected browser journeys pass, including eight account journeys. They cover
  import, rename/membership/reload, logout/account switch, two browser contexts,
  stale writes, delayed reads, session-error recovery, failed loads, bounded recovery
  and mobile/password-manager behaviour.
- The frontend build passes. Both code-review axes found and verified fixes for
  cookie/read ordering, expired CSRF recovery, normalized rate-limit identities,
  test-database isolation and malformed CSRF handling.
- Live HTTP checks verify separate anonymous-cookie issuance, no cookie rewrite on
  repeated reads, anonymous personal access returning 401 and private no-store
  headers. Account registrations in tests use disposable databases; the assistant
  did not create a permanent account in the user's live database.
- All eleven movie banks and the independent script/Inception policies are unchanged.
  No local-model calls were needed. Local proof: `.cache/proof/account-runtime.json`,
  `account-mobile.png` and the live account screenshot.

Tests prove these code behaviours, not a complete production security certification
or model accuracy. Hosted password recovery, email verification, OAuth/passkeys/MFA,
quiz-attempt history, notes, broader preferences, community and deployment/load
qualification remain separate work.

## Production configuration

For local development, defaults use loopback HTTP at `http://127.0.0.1:5173`.
An HTTPS deployment must set its exact `FRAME_APP_ORIGIN` and
`FRAME_SECURE_COOKIES=true`. The server rejects an HTTP non-loopback origin or
mismatched HTTPS/cookie settings. `FRAME_ACCOUNT_DB` can select a private persistent
storage path. See `backend/.env.example`; do not put credentials in frontend env vars.

This is a local account system with no mail service or recovery flow yet. Public
rollout needs deliberate recovery, backup, proxy/throttling and multi-user deployment
work; the new screens do not imply those milestones are complete.

## Questions and answers

**Why not use JWT?** An opaque server session makes logout/revocation simple and
keeps permissions/expiry under server control. JWT adds no needed capability here.

**Can a user submit someone else's ID to access their collection?** Owner IDs are
not accepted in mutation bodies. The backend gets the owner from the verified
session and scopes its SQLite lookup/write to it.

**Why isn't checking the account ID enough?** Two tabs for the same account can still
race. The account ID prevents mixing users; the revision prevents stale updates.

**Why import explicitly?** Browser saves may come from a shared machine. Automatically
importing them into every account would copy data the account holder did not choose.

**Why do we keep both guest and account storage?** Guests can keep browsing/saving
without signing up, while account holders get durable backend persistence. Keeping
the two separate also prevents private saves leaking into a shared guest browser.

**Does this use RAG or agents?** No. Identity, permissions and persistence need exact
code and tests. Future private memory must use the authenticated owner and explicit
preferences; credentials and session values must never enter public retrieval.
