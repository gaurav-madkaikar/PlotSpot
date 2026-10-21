# Script context connected to story generation

Approved: connect script retrieval to quiz/discussion, corroborate against released-film evidence, and evaluate before enabling. Execute inline; preserve unrelated edits, no commits.

Design: use the existing Wikipedia plot source as released-film evidence, reviewed IMSDb snapshots as supplemental draft context. Retrieve both with exact identity/offset checks. Generate at most two proposed quiz questions per request, each with literal quotes in both sources. A separate constrained reviewer assesses released support, script agreement, objective wording, plausible options and exactly one correct answer. Code owns the final accept/reject decision. Keep quiz citations tied to Wikipedia; record script provenance in private traces. Discussion follows the same evidence gate, explicitly labels interpretations, and displays draft provenance separately from supporting citations. Early scripts must not supply unsupported film events. News/facts generation is unchanged.

Rollout: freeze policy implementation before a new labeled local-model evaluation; require all reject/uncertain cases withheld and at least 75% positive cases accepted. Failed/malformed cases count in totals. A digest-bound gate controls the script path; fail closed to the existing path when the gate is absent/invalid. Never enable from unit tests alone. Evals are limited authored cases, not a claim of production safety.

Tasks:
- [x] Implement strict cross-source draft/assessment contracts and model boundary with deterministic source/quote validation.
- [x] Implement two-source retrieval/generation orchestration, header exclusion, persistence of metadata traces.
- [x] Connect to more-quiz and unrestricted movie discussion flows, preserving consent/shared slot/deadlines/concurrent-write checks; retain curated internal paths.
- [x] Add source-context UI using existing light styling and strict URL validation; validate browser journeys.
- [x] Add malformed/contradiction/injection/single-answer/fallback tests, freeze policies and run fresh labeled evals and real movie smoke checks.
- [x] Record evidence, limitations, learning note and rollout decision; restart live backend if enabled.

Modules: story_verification.py (contracts/prompts/acceptance), story_rag.py (retrieval and orchestration), scripts/evaluate_story_gate.py (evaluation and implementation-bound gate), tests/test_story_rag.py and e2e/movie-questions.spec.ts. Existing service source loader is extracted for reuse. Gate fingerprints cover both modules and screenplay retrieval/source modules.

Outcome: integration and verification complete; implementation gate enabled for three registered scripts. 639 backend checks, 57 browser checks and frontend build passed. Final verifier regression matched 20/20 consumed labels. Real Inception discussion succeeded, but final new-quiz trial retained 0/2 proposals; previous real trials also retained none. Quiz-generation usefulness is an explicit remaining quality limitation, not a passed production-readiness criterion. See lesson 44 and versioned reports.
