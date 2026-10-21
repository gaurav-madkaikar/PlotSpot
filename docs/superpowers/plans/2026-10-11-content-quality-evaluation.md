# Content quality evaluation and critic revision

Continue the approved movie-content pipeline before publication jobs. User delegates coding and checks to the assistant.

Freeze 18 development cases (the previous six plus twelve quality/context cases) and twelve reserved cases using different fictional sources. Cases cover supported unusual background, supported qualifiers, ordinary metadata, unsupported qualifiers/causes/numbers, plot misclassification, wrong answers, weak/ambiguous distractors, missing context, subjective symbolism and retrieved instructions. Labels are authored expectations, not independently collected human annotations.

Record the existing critic baseline on development cases, revise its policy using development errors and previous real-draft observations, then evaluate the revised policy on development and once on the reserved partition. Do not revise against held-out outcomes during this stage. Report exact matches, false approvals, useful approval coverage, false refusals, errors, per-category counts, latency and dataset/model/policy identity. Failed/unfinished cases remain in denominators. A completed evaluation is not a passing quality gate.

- [x] Freeze separate labelled partitions.
- [x] Implement bounded validated evaluator with atomic reports and failure accounting.
- [x] Test labels, disjoint partitions, metrics, metadata, model failures and deadlines.
- [x] Preserve actual existing-policy development baseline.
- [x] Test a clarified critic policy; reject it when measured behavior regresses.
- [x] Run revised development and selected-policy reserved evaluation; preserve all mismatches.
- [x] Update learning/progress documentation with actual results and limitations.

No publication, viewer-facing jobs, source fetching or UI changes in this slice. Automatic preparation remains gated pending quality findings; these small synthetic partitions are not a production-readiness/security certificate.

Results: v1 development 12/18 label matches, 4/5 useful approvals, 4/13 false approvals (58.46s). Candidate v2: 8/18 matches, 2/5 useful, 6/13 false (63.57s). The development regression gate rejected v2. Restored v1 fingerprint exactly matches the baseline; both policy artifacts are archived. Selected v1 reserved run: 6/12 matches, 3/4 useful, 4/8 false (43.25s). No inference/validation errors in these observations. Reserved cases were evaluated once without subsequent tuning; they are now consumed and future tuning requires fresh reserved cases.

Validation: 534 backend checks passed. Lesson 38 explains behavioral labels, metrics, regression selection, real failures and the publication boundary. Next: structured support/content/answer checks with explicit selected-answer mapping; retain these cases as regression evidence rather than claiming successful quality improvement.
