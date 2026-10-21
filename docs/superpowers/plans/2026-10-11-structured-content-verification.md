# Structured content verification

Continuation of the approved quality-gated movie pipeline. User delegates implementation and checks.

Implement an optional verifier alongside the unchanged baseline critic. Deterministic checks remain first. Pass explicit selected-answer text and indexed choices to a bounded local model. Request separate support, suitability, supported-choice indices and distractor-plausibility assessments; code derives accept/reject/uncertain and cannot be overridden by model-supplied decisions. Persist all criteria in evaluation reports. Preserve baseline routing/default until development comparison justifies selection.

Compare against the frozen 18-item development baseline. Freeze twelve fresh reserved cases before observing structured development results; the previously consumed reserved cases are not an unseen evaluation. Evaluate only the selected frozen verifier on the fresh reserved set and do not tune against that outcome. Report quality, useful coverage and errors; no publication authority follows from selection.

- [x] Add structured assessment contract and code-owned decisions.
- [x] Add explicit indexed choices/selected answer and local-only structured call.
- [x] Extend evaluator with optional verifier selection and criterion traces.
- [x] Freeze twelve new reserved items.
- [x] Test answer mapping, criterion conjunctions, invalid indices/IDs, missing outputs, bad evidence and client restrictions.
- [x] Finish actual development comparison and select policy without regressions.
- [x] Evaluate selected frozen verifier once on fresh reserved cases.
- [x] Preserve policy artifacts, reports, learning/progress notes and validation.

No UI, source-fetching or automatic publication changes. The structured verifier is still a fallible model assessment, not a semantic truth guarantee.

Implemented three measured candidates: v1 combined assessments (12/18 matches, 4/5 useful, 5/13 false approvals); v2 separated calls but shared categories (12/18, 1/5 useful, 2/13 false); v3 distinct prompts and branch-specific schemas (13/18, 4/5 useful, 4/13 false). V3 passed the relative development gate against baseline 12/18, 4/5 useful, 4/13 false.

Fresh reserved: baseline and v3 both matched 7/12, approved 3/4 useful items and 3/8 invalid/uncertain items. V3 took 86.91s versus baseline 43.02s. Keep structured optional; default remains baseline. No automatic publication approval. Baseline reserved scores were not inspected until v3 was frozen; both policies ran once and no changes followed reserved outcomes. This set is now consumed.

561 backend checks passed. The optional `--verifier structured` also works in the bounded draft-preparation command, with full criterion traces and at most two specialist calls per batch. Lesson 39 explains mapping, typed criteria, code decisions, all experiments and limitations. Next useful product work: preparation progress and reviewable drafts, with publication remaining controlled.
