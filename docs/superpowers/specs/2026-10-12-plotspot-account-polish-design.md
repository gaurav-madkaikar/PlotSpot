# PlotSpot identity and account polish

The user explicitly requested these five changes and authorized direct implementation.

- Center the native trailer dialog horizontally and vertically, keeping its responsive size, internal scrolling, Escape dismissal and focus return.
- Use a reel SVG and the PlotSpot wordmark across public application copy, browser metadata and favicon. Header navigation says Collections without a count.
- Guests hold saves, named collections and spoiler preferences in document memory only. SPA navigation keeps them; refresh/new tabs discard them. Existing browser persistence is retired. Show a concise Sign in to keep your saves prompt. Signed-in snapshots stay private and durable. Importing temporary guest saves remains an explicit action after sign-in.
- New registration requires a validated email and a one-use, 30-minute verification link before login. Verification does not automatically authenticate. Preserve existing username-only accounts and their collection ownership through a nullable-email migration.
- User selected local verification previews. Explicit preview mode is permitted only for loopback HTTP development, labelled as a preview rather than delivered email. Public configuration fails closed without mail delivery; support an SMTP TLS transport for later deployment. Store only verification token hashes, use URL fragments to avoid access-log leaks, enforce CSRF and rate limits, and do not log credentials or tokens.

Acceptance: browser tests for modal centering, branding/navigation, temporary saves disappearing on reload, verified accounts retaining saves, explicit guest import, email form/preview/verification/login and mobile overflow; backend tests for expiry/reuse/resend, invalid inputs, mail failure and migration. Movie content banks and ingestion policy remain untouched.
