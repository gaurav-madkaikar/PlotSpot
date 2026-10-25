# Account, Collections and footer layout

The user authorized direct UI changes: simplify Sign in and remove temporary-save content; replace the unprofessional footer copy and tagline; use /collections; remove repeated All saved and fragmented intro copy.

Use the existing warm paper/ink/accent palette. Center the guest account form in a narrow column, reduce headline scale, remove the marketing aside and all temporary-save UI from /account. Move explicit guest import to the signed-in Collections page so previously authorized preservation remains available. Do not automatically merge into an account.

Use “Discover films, explore their stories” for the header tagline. Replace the large slogan footer with a compact product identity, navigation and factual TMDB/demo attribution, retaining an About link for full attribution.

Make /collections the canonical UI path. Redirect /collection with replace semantics while preserving search parameters/hash; update consumer navigation and safe returnTo handling. Backend /api/me/collection and module import names remain unchanged. All saved appears once in the collection selector; the default content toolbar shows only the film count. A selected named collection may have its own heading and management controls. Guest intro is a single concise sentence with a sign-in link; keep the refresh-lifetime explanation once on Collections, not on Sign in.

Verify login/registration/verification, explicit import on Collections, create/rename/delete/membership, old-path deep-link redirects, mobile layout/keyboard navigation, revised footer and no duplicated All saved heading. No backend, AI generation or content banks change.

## User correction

Account access must follow the shared left page gutter, retaining a narrow form column. Hide zero film counts/badges, remove guest refresh-warning copy throughout consumer UI, and place enlarged icon-only rename/delete controls beside the selected collection name. Preserve accessible names, 44px targets, keyboard behavior and deletion confirmation.

## Wide form correction

The user requested that Sign in/Create account extend horizontally to reduce unused page space, with a dark footer on account access. The account access card spans the shared content area, retaining left alignment. Desktop uses two sign-in field columns and three registration columns; tablet registration uses two columns with a full-row password field; mobile stacks. Error/submit controls occupy full grid rows with a bounded desktop button. The account route selects an ink footer variant using existing on-ink tokens. Preserve user-edited copy.
