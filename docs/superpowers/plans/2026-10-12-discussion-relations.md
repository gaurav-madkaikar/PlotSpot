# Discussion identity and relation support implementation plan

**Goal:** Supply source-backed name context and improve rejection of unsupported
causal explanations while preserving bounded local discussion and saved content.

**Architecture:** Keep original retrieval anchors/vectors. Add at most one exact
same-section sentence connecting a proper-name token in the question with a
different proper-name token in an anchor, only for an unambiguous adjacent name match.
Use its original source-window provenance, reserve generation/citation budgets,
and include it in the semantic review and final citations. Ask the distinct
reviewer to derive the evidence answer/quote before judging the proposed answer;
validate its exact quote choice, keys, bounds and verdict in code. After observing
the first candidate omit a required detail, recover at most one additional
complete offered sentence containing two missing answer terms, retaining its
original IDs. This is lexical context recovery, not semantic verification.
At most five review inputs and three final citations; overflow abstains.

**Alternatives:** Merely changing instructions offers no source-backed identity
repair; another larger model adds hardware costs without fixing missing context.
Selected approach keeps existing two local chat calls and makes the reasoning
contract inspectable. Proper-name matching is a bounded context heuristic, not
an identity authority. Ambiguous or missing matches do not authorize an alias.

**Constraints:** Execute inline under existing user authorization. No new tools,
framework dependencies, agents, publication, commits, worktrees or UI redesign.
Adult/search preferences, banks, script policies and account scope are preserved.
No universal entailment/safety or production-qualification claim.

- [x] Freeze the Lesson 59 context/generator/reviewer baseline; freeze additional
  fictional relation/name controls before candidate outputs. Preserve old labels.
- [x] Add bounded same-source/section name context with original citation IDs.
  Test unknown/ambiguous names, wrong movie/revision/spoiler, budgets and source
  coverage. Pass optional question into context recovery from the real pipeline.
- [x] Implement structured evidence-first reviewer contract and exact quote
  validation, retaining cancellation/error/abstention behavior. Compare fixed
  controls; retain unsuccessful variants without rewriting expectations.
- [x] Extend the development runner to load the frozen Lesson 59 baseline and
  compare all seventeen existing cases with final stable candidate code. Check
  module hashes before/after evaluation and record reviewer assessment traces.
- [x] Run backend and focused browser checks, restart owned backend, verify
  Arrival/Dent and spoiler behavior live, preserve banks/script gates, record
  a UI proof, restore the user's spoiler preference and update Lesson 60/docs.

**Learning:** Missing context versus model error; context heuristic versus
identity proof; extracting a stated reason versus associating nearby events;
strict structured review and exact provenance; honest baseline/latency reports.
