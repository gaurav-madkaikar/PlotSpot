# Multi-movie saved content implementation plan

**Goal:** Extend approved reusable facts/story quizzes to Inception, Arrival and The Matrix, retaining Interstellar's current publication.

**Architecture:** A reviewed JSON bank contains authored stems, distractors, concise explanations and evidence markers. A compiler binds every entry to the selected movie's reviewed, section-aware Wikipedia revision. An explicit preparation command fetches or reads a snapshot and atomically publishes a complete collection. No viewer request triggers generation. This baseline is curated content, not a multi-agent or general web-research pipeline.

**Constraints:** Ten unique scored story questions and at least five unusual background facts per added movie. Plot only for quiz; production/casting/filming/music/effects for facts. Unknown spoiler classification remains gated. No early screenplay evidence, adult filtering, new model dependencies, commits or unrelated worktree edits. Existing publications are retained unless refresh is explicit; failed checks leave them intact.

- [x] Add reviewed content banks for movie IDs 27205, 329865 and 603 with section-specific evidence markers.
- [x] Generalize compilation without changing Interstellar's bank; citations include movie/source/revision-derived passage IDs and bounded complete sentence evidence.
- [x] Extend preparation CLI with `--movie-id`, optional saved source snapshots, clear retain/fetch/validate/publish progress and an optional JSON report. Reject unreviewed IDs and snapshot identity mismatches before publication.
- [x] Test all banks, wrong source identity, missing/changed markers, section misrouting, citation bounds, retained publications, failed refresh and saved API reads without AI/source calls.
- [x] Publish all three using real saved revisions, verify source/quiz/fact content manually, validate backend and frontend, check live UI and record learning notes and scope limits.

Validation: 458 backend checks, production build and ten focused browser journeys passed. Initial browser launch was missing the project browser-cache environment; corrected command passed. Live Inception facts/quiz/scoring verified. Publication reports record the real revisions and zero model calls; learning note 35 documents that this is a curated baseline. Live servers restored.

Future slice: general local-model content proposals, stronger claim/ambiguity evaluations and parallel orchestration. More-question generation remains supported only where unused reviewed targets exist; no invented questions to fill a quota.
