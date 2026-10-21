# Bounded source-based content preparation

Continuation of the approved evidence-grounded movie pipeline. User delegates implementation and validation; no further coding exercise is assigned.

The previous critic accepted plot content carrying an incorrect background label. Derive labels from classified source sections and verify the original character span before generation. Section provenance constrains routing but cannot prove semantic truth. A production paragraph can still mention plot events.

Implement a separate draft preparation command before connecting viewer requests or publication. It reads a registered source snapshot, selects complete bounded sentences in story/background branches, and performs sequential local generator/critic calls. Round-robin background sections for coverage; cap eight batches and enforce an overall deadline. Stop at five retained fact drafts and ten question drafts, or return incomplete without inventing content. Filter overlapping wording/reused quotes across batches. Save a separate atomic JSON checkpoint after each completed batch, including rejected drafts and exact provenance. Critic acceptance does not grant publication rights.

- [x] Add source-derived evidence origins and snapshot verification.
- [x] Add bounded generation/review coordinator and separate checkpoint command.
- [x] Test wrong routing, altered evidence, source identity, budgets, incomplete/rejected batches, cross-batch duplicates and failures.
- [x] Run local-model preparation against the saved Inception article; preserve actual results, including failure.
- [x] Update learning/progress records with observations and limitations.

Scope: no frontend changes, publication writes, automatic retry, source fetching, arbitrary URLs, or claims of semantic deduplication. The existing app continues to serve its reviewed saved collections. Draft checkpoints preserve partial output but are not a resumable job queue. Resume/idempotency, broader held-out quality evaluation and viewer-facing jobs remain subsequent integration work.

Real Qwen generator/critic baseline: six completed batches, five retained fact drafts and five question drafts, incomplete at the 360-second deadline. Manual observations flag ordinary production metadata and an unsupported restrictive qualifier despite critic acceptance. No publication occurred. After the baseline, added and tested an early stop when remaining passages cannot serve unmet targets; preserved baseline timing predates that optimization. Backend validation: 510 checks passed.
