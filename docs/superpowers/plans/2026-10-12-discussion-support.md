# Complete discussion context and support checking

**Goal:** Repair the observed makeup citation and reject answers whose selected
evidence does not support the requested claim, within bounded local inference.

**Architecture:** Retain stored character windows and embeddings. Attach validated
source locations at snapshot read. Recover complete sentences overlapping the
top-three retrieval anchors, drawing only from eligible windows in the same
revision/section. Keep at most six generation windows and three final citations;
reject oversize/uncovered sentences rather than inventing a boundary. Offer
verbatim sentences with code-owned window provenance. After generation, a
separate bounded local support call reviews only the question, answer and selected
sentences; unsupported/uncertain results abstain. Structural failures propagate
through existing recovery UI. This model verdict remains fallible.

**Constraints:** No re-embedding, modified saved banks, script gate changes,
arbitrary URLs, semantic movie discovery, executable model tools, accounts or
automatic publication. Current user approval continues implementation inline;
no commits, delegated agents or repeated generic approval gates.

- [x] Preserve the current hybrid/excerpt pipeline as a developer-only baseline.
  Freeze support-check cases before model outputs, including correct statements,
  wrong entity/reason/time/negation/number and untrusted instructions.
- [x] Add source locations without changing persisted snapshot identities or
  original passage text/vectors. Test sentence extraction across adjacent windows,
  movie/revision/spoiler/section isolation, context/citation limits and tampering.
- [x] Add code-owned complete-sentence options, map each to original contributing
  IDs and integrate a strict supported/unsupported/uncertain local review. Test
  malformed verdicts, rejection/abstention, quote membership and cancellation.
- [x] Compare with the frozen current pipeline on the unchanged seventeen
  development cases. Record initial top-three retrieval separately from expanded
  generation evidence. Inspect failures without relabelling historical cases.
- [x] Run backend/browser checks, restart the owned local service, verify the
  makeup answer and spoiler behavior live, preserve banks/script qualification,
  update learning notes/checklist/progress and remove temporary test files.

**Learning:** indexing versus context recovery; exact offsets and source identity;
structural validation versus semantic support; generator/verifier errors;
false acceptance versus false rejection; latency and honest development metrics.

## Delivery result

Complete sentence/provenance recovery and a separate local support review are
live in Wikipedia discussion. 1,002 backend checks and sixteen focused browser
checks pass. Final frozen-code comparison: 16/17 versus 15/17 hybrid baseline.
Arrival identity-context rejection and a causal-control false acceptance are
retained and documented; this is not production or publication qualification.
All eleven saved banks and the existing script gate are unchanged. Live HTTP/UI
checks confirm makeup citations 073+074, Dent's stated reason and spoiler consent.
Lesson 59, checklist, progress and reproduction/inspection reports are updated.
Temporary browser-test configuration removed; original spoiler setting restored.
