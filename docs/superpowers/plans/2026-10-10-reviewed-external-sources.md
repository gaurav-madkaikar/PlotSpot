# Reviewed external sources implementation plan

Approved scope: source connector items 2–3 from story-quiz plan, with one reviewed background claim.

Goal: publish a sixth sourced production fact and offer a clearly labelled early screenplay link without altering saved quiz additions.

Architecture: fixed source registry drives bounded HTTPS reads; Caltech JSON metadata becomes validated effects evidence; IMSDb inspection produces provenance only, never quiz passages. Explicit preparation appends a reviewed claim to existing SQLite content using optimistic concurrency. Mixed-source publication records an exact revision manifest. Model outputs and viewer requests cannot choose URLs.

- [x] Add exact citation URL policy shared with reviewed source registry; retain Wikipedia revision links.
- [x] Fetch bounded Caltech record metadata, validate record ID/title, extract publisher/authors/date, hash snapshot, compile a short attributed fact only when reviewed evidence matches.
- [x] Inspect IMSDb title/date in the screenplay header; retain metadata/hash and exclude early/unverified scripts from scored quiz retrieval.
- [x] Extend SQLite publication with an exact revision manifest; preserve it during question expansion.
- [x] Add explicit preparation command that preserves quiz/questions and existing facts, adds provenance links, and leaves publication intact on source failures.
- [x] Extend frontend citation validation and Facts source links; retain spoiler consent and source attribution.
- [x] Verify adapter boundaries, title/date mismatches, mixed-source persistence, failed updates and browser rendering. Save learning note and real-source report.

Constraints: reviewed IDs only; HTTPS fixed hosts/paths; no redirects; bounded streamed bodies/timeouts; no model capabilities or arbitrary fetch URLs; no full script storage/publication; original saved quiz stays intact; sources are production background rather than live news; no claim of general autonomous fact verification.
