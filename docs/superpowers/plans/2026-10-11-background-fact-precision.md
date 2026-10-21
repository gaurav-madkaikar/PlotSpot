# Background Fact Precision Implementation Plan

Execute inline under existing implementation authorization; no delegation or publication.

**Goal:** Detect factual wording drift and missing entity context in background proposals without changing story/quiz policy.

**Final architecture:** Retain the existing semantic critic and add a bounded background-only wrapper for source-local multiword-name checks on factual bodies. Keep exact quotes and eligibility owned by code; record assessments, fingerprint the helper, and recheck evidence during explicitly inspected publication. Two model criterion experiments failed usefulness checks and were abandoned with preserved results. Editorial titles stay under semantic review.

**Tech stack:** Existing Python/Pydantic/httpx/Ollama clients, pytest, local qwen3.5:9b and cached evidence.

- [x] Freeze `precision-dataset-v1.json`, snapshot identities and saved/story preservation hashes. Six accepted controls, eight rejected distortions and four missing-name uncertain labels over consumed source excerpts.
- [x] Run original critic once: 14/18 labels, all six useful accepted, two false approvals. Preserve distinct baseline and failed variants.
- [x] Add `background_fact_review.py`: validate background-only evidence, exact unique ID completeness, deterministic quote gates, source-local name checks and code-owned mapping. Record semantic decision/missing mentions; fingerprint helper in background workflows only.
- [x] Improve writer precision instructions and bounded same-section preceding sentence context within 600 characters.
- [x] Add contract checks for mapping, local-only clients, missing/duplicate/unknown IDs, source context, registered titles, editorial heading casing, publication assessment tampering/name rechecks and background-only fingerprints. Final full suite: 837 passing.
- [x] Evaluate alternatives on consumed labels: v1/v2 overreject; v3 18/18 but generation exposes heading bug. Final v4 deterministic replay remains 18/18 and transparently reuses v3 semantic judgments with no model calls. Fresh final generation: seven proposals/four eligible, no errors. Inspect all seven; three supported and known semantic/wording limits recorded.
- [x] Inspect final cached Arrival publisher RAG: four proposals/two eligible, zero errors. Article/vector caches reused; inspect each output and record combined-claim, title, duplication and wording limitations without publishing.
- [x] Confirm all ten saved content rows and story fingerprint unchanged after all model runs. Document findings and limitations in lesson 53, eval README and progress.

Final artifacts: `precision-final-inspection.json`, `precision-final-replay-v4.json`, `precision-final-generation-v4.json`, `precision-preservation-after.json`, `arrival-fact-precision-v4.json` and its inspection. These establish development observations and preserved state, not held-out accuracy, catalog-wide qualification or new consumer content.
