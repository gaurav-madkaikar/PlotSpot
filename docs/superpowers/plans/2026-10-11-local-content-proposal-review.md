# Local proposal implementation and review

User delegates implementation and checks to the assistant moving forward. Preserve explanatory learning notes; do not assign further coding exercises unless requested.

**Scope:** Finish the structured local proposal function, integrate an independent draft critic into the existing read-only runner, and evaluate labelled quality cases before connecting publication jobs. This is one implemented pipeline stage, not arbitrary-movie automatic preparation.

- [x] Implement evidence-only proposal prompt, alias-constrained schema and structured parsing with fixed local-client validation.
- [x] Add independent critic with deterministic rejection precedence and exactly one validated judgement per remaining candidate.
- [x] Bound output tokens and disable Qwen thinking for structured calls, preserving existing helper defaults.
- [x] Add contract/failure checks and run real generator/critic with saved Inception evidence.
- [x] Run the fixed authored development suite; preserve model failures and limitations.
- [x] Update learning/progress documents and record validation.

Real smoke: llama3.2:3b generation plus qwen3.5:9b critique completed in 32.6 seconds. All four drafts passed deterministic checks; critic rejected two facts and accepted two questions. Human inspection still finds weak distractors, so critic acceptance is insufficient for publication. Earlier Qwen thinking run produced an empty assistant string and failed closed; non-thinking/output bounds completed. No published collection changed.

Validation: 487 backend checks passed. Six fixed authored critic-development cases matched expectations in five cases, taking 13.22 seconds. Miss: accepted plot content labelled as background. Exact failure preserved in `evals/movie-rag/content-review-ollama.json`; no held-out/general-safety claim. Learning note 36 and progress record updated. No frontend or live-server changes were needed.
