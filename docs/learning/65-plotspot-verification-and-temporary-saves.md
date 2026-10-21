# 65. PlotSpot identity, verification and temporary saves

The movie companion now uses PlotSpot and a film reel SVG. Collections navigation has no saved count. The trailer dialog explicitly sets fixed positioning, inset zero and automatic margins; this centers it even when the CSS reset removes browser defaults. Its maximum height uses dynamic viewport units so the content scrolls on short screens.

## Why memory rather than sessionStorage?

`frontend/src/lib/collection-storage.ts` keeps a module-local `guestState`. React routes change the visible component without reloading JavaScript, so it survives navigation and provider remounts. Refresh loads a new document and creates an empty state. Both localStorage and sessionStorage survive refresh, so neither matches this requirement. The historical app-owned guest localStorage key is retired; unrelated browser preferences are untouched.

Guest saves show a Sign in to keep them prompt. Signing in does not silently merge guest data into whichever account happens to open. The Collections page offers **Keep these saves** after sign-in. A successful import clears the temporary cache; account snapshots persist privately in the backend. Guest spoiler preferences also last only for the current page visit; signed-in preferences remain durable.

## Why isn't an email field enough?

Format validation answers “could this be an email address?” Ownership verification answers “can this person receive the verification link?” The backend uses email-validator without a DNS lookup for syntax/normalization; a verification token proves ownership in SMTP mode. Local-part comparison is case-insensitive by application policy. Provider-specific dot/plus transformations are not used. Existing username-only accounts remain accessible with their original owner IDs; new registrations require email.

`accounts.register()` hashes the password, inserts an unverified account, stores only a hash of a random verification token and returns a verification receipt. It does not create a signed-in session. Login refuses unverified accounts. The link expires after 30 minutes. `verify_email()` checks its hash and expiry, marks the account verified and removes the token in one transaction. Reuse fails; verification never switches the current account session.

The token is in the link's URL fragment, which browsers do not send in HTTP request URLs. The account page captures it in memory and replaces the address immediately. Clicking **Verify email** sends it in a CSRF-protected POST body. Merely opening a link does not consume it, so email link scanners cannot verify an account accidentally.

## Local preview versus email delivery

You selected a local verification preview. `PLOTSPOT_VERIFICATION_MODE=preview` is enabled in the local backend configuration. Registration displays **LOCAL EMAIL PREVIEW** and explicitly states that no email was sent. Open the link, verify, then sign in. This is a development simulation and does not prove access to a real inbox.

Preview mode rejects public/HTTPS origins and the development server binds loopback. A public deployment must use `PLOTSPOT_VERIFICATION_MODE=smtp`, an exact HTTPS app origin, secure cookies and a configured SMTP sender/host/credentials. Configuration names are in `backend/.env.example`; secrets stay in the ignored local file or deployment secret manager. SMTP uses STARTTLS or SSL with certificate validation. Disabled delivery fails closed, and delivery errors are bounded, generic and do not log addresses/tokens.

Resend requires the account's username and password. Durable client/account limits and a per-account cooldown prevent email flooding. A short database transaction reserves the resend; SMTP runs outside the SQLite write lock; success atomically replaces the old hash. Failure preserves the old link. This keeps a slow mail server from blocking other users' collection access. Mail is synchronous in this local milestone; worker queues/retries and measured SMTP throughput remain deployment work.

## Checks and boundaries

Browser checks cover responsive centering, keyboard dismissal, branding/navigation, temporary state surviving navigation and clearing on reload, account persistence, explicit import, email validation, local preview and verification while another account is already signed in. Backend checks cover one-use/expired links, resend/cooldown/concurrency, malformed emails, mail failure, legacy migration, TLS transport and production preview rejection. These are application tests; they do not measure AI/RAG quality. No movie facts, quizzes or script policies changed.

References: [OWASP email validation and verification](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html), [email-validator documentation](https://github.com/JoshData/python-email-validator), [Python SMTP documentation](https://docs.python.org/3.12/library/smtplib.html).

## Layout update and route naming

Sign in now uses a form aligned with the shared left page gutter with no temporary-save section, banner or marketing aside. The explicit import action moved to Collections, close to the saved films it changes; it still requires a user action. Signing in from Collections returns there without reloading the document, so the visit’s guest cache can be imported.

The canonical browser route is `/collections`. A small React Router Navigate component redirects the historical `/collection` path using replace semantics and retains its query parameters, hash and navigation state. UI links changed; the private `/api/me/collection` API and code-module import paths remain singular because they serve different purposes. The default All saved label appears in the selector once, with a separate film-count toolbar. The footer uses compact navigation and factual data attribution.

The latest UI correction keeps empty collection counters hidden and removes guest refresh-warning copy throughout the UI. This changes presentation only: document-memory guest saves still clear on refresh. Rename/delete remain keyboard-operable, with accessible labels and native title hints, while their 21px icons replace visible text beside the collection title.

The account access card now spans the shared content area. CSS grid puts username/password side by side for desktop sign-in, and username/email/password in three columns for desktop registration. Tablet and mobile breakpoints preserve readable labels, hints and touch targets. Full-row error messages and submit controls do not compete with field columns. The account route selects a dark footer variant in Shell; authentication/API behavior is unchanged.
