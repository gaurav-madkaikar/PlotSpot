# Persistent movie content implementation plan

Goal: Show saved collections of at least five production facts and ten distinct scored story questions without generating on each view.

Architecture: reviewed Interstellar content bank plus source-evidence compiler writes one validated, versioned SQLite collection atomically. Read endpoints return saved content only. Preparation is a separate local command, not a viewer action. Existing learner RAG remains active in Discuss. Starter wording/options/explanations are curated; this is not general AI question generation.

- Expand reviewed banks to ten scored story items, one unscored reflection, five non-plot facts.
- Add compiler validating unique IDs/questions/options, supporting source statements, minimum sizes, revision citations and metadata.
- Add SQLite store with atomic publication, version/date/source metadata, idempotent preparation and explicit refresh; failed refresh preserves prior content.
- Read-only GET endpoints check spoiler consent before returning saved content. Retain POST compatibility as reads only. Missing collections disclose coverage without triggering generation.
- Auto-load saved panels after consent; retries repeat reads, replay changes local choices only.
- Prepare Interstellar from the previously fetched real source snapshot. Save private source and SQLite files outside versioned source code.
- Test persistence across store instances, no generation during reads, incomplete/duplicate rejection, failed refresh preservation, permission gate, larger UI collections and replay; build and verify browser.
