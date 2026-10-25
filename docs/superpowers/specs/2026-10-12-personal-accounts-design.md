# Local accounts and durable personal collections

Implements the next approved milestone under the original design's local
username/password, HTTP-only sessions, CSRF and owner-isolation decision. The user
has authorized continuing implementation and handling coding/checks directly.

Use the existing FastAPI/React/SQLite stack and editorial light design. Local
accounts avoid paid identity providers; hosted OAuth would add external setup,
and extending browser-only storage would not provide durable account isolation.

## Scope and contracts

- Guests retain the existing browser collection key/behaviour. Account data never
  enters that key. Signed-in state is loaded from an owner-scoped private SQLite DB.
- `GET /api/auth/session` bootstraps a short anonymous session for CSRF and returns
  the current user plus a synchronizer token. Register/login rotate the cookie;
  logout revokes it and returns a fresh anonymous envelope.
- Usernames: normalized ASCII 3–32 characters, letters/numbers/underscore/dot/hyphen;
  uniqueness is case insensitive. Passwords: 6–128 characters, <=512 UTF-8 bytes,
  no silent trimming/truncation. Argon2id m=19456 KiB, t=2, p=1 with random salts.
- Random opaque session tokens are stored only as SHA-256 hashes. Cookies are
  HTTP-only, SameSite=Strict, Path=/; HTTPS mode also uses Secure and __Host prefix.
  Anonymous bootstrap uses a separate HTTP-only cookie; existing-session reads
  do not set cookies, so a delayed read cannot undo authentication rotation.
  Authenticated expiry seven days, idle expiry one day, anonymous expiry ten minutes.
- All unsafe auth/personal requests require exact configured Origin and the
  session-bound CSRF header. JSON only, <=128 KiB; errors must not echo credentials.
  Private responses have Cache-Control:no-store. No CORS broadening.
- Durable login/register attempt limits per client and client/username precede
  password work; unknown users use a dummy hash and generic credential errors.
  Session cleanup/caps bound anonymous rows and active sessions per account.
- `/api/me/collection` GET/PUT returns saved/watched/custom collections plus revision.
  The owner always comes from the session. PUT requires expected revision and
  atomically increments it. Stale writes return 409, preserving the stored state.
- At most 2000 saved/watched movie IDs, 50 collections, 4000 membership entries;
  positive 32-bit movie IDs, unique collection IDs/names, normalized 60-character
  names, reserved All saved, and custom membership subset of saved are validated.
  Removing a custom collection leaves its films in All saved; removing a saved
  film also removes its custom memberships. Watched/spoiler state stays independent.
- Explicit browser import merges saved/watched IDs and collections by normalized
  name. New IDs are server-generated. It checks revision, is membership-idempotent,
  and leaves the guest browser data intact. No automatic import on login/signup.
- React account identity switches remount the personal provider; loading/session
  failures do not expose previous owners' state or write guest fallback data.
  All persistence mutations show busy/error feedback and commit visible state only
  after success. Cross-tab/focus session changes revalidate identity; active account
  errors trigger session refresh. Guest storage sync remains supported.
- Add `/account`, Sign in/Account header entry, labelled accessible form, password
  visibility and autocomplete/paste support, signed-in overview, import and logout.
  No new dark theme, consumer drafts or mandatory-login wall for discovery.

## Verification and limits

Tests must cover rotation/revocation/expiry, password storage, generic failures,
rate limiting, CSRF/origin/body limits, secret-free errors, owner isolation, CAS
conflicts, import name collisions/idempotence and persistence after reopening DB.
Browser checks cover guest preservation, account save/reload, logout/account switch,
explicit import, named-collection changes, stale writes and failed loads. Existing
movie/discovery checks and published-bank/script fingerprints must remain intact.

Add Lesson 64 tracing identity, cookie, CSRF, state ownership and migration. Email
verification/recovery, OAuth/passkeys, MFA, community, memory and deployment/load
qualification are separate milestones. Public deployment requires HTTPS cookie
mode and the exact app origin; reverse-proxy/distributed throttling remains future
work. No existing user credentials or permanent demo accounts are created by the
agent; tests use isolated disposable databases.
