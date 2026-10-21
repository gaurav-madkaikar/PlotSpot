# Content evidence retrieval implementation plan

> Execute inline using executing-plans. User has approved the RAG flow and delegated implementation and checks. Preserve the existing working checkout and do not commit unrelated work.

**Goal:** Connect persistent local embeddings to bounded fact/quiz draft preparation.

**Architecture:** Reuse EvidenceStore and ingest_source for section-aware source windows. Embed a fixed set of story/background topic queries, filter by purpose before ranking, and select unused complete sentence groups supported by ranked windows. Retain exact provenance and retrieval traces. Draft preparation keeps its critic, deadline, quotas, checkpoints and publication boundary.

**Tech stack:** Python, httpx, Ollama nomic-embed-text:v1.5, persistent Chroma, existing Qwen generator/critic.

## Constraints and scope

- Only validated registered Wikipedia snapshots in this increment; no script ingestion or arbitrary URL fetching.
- Source revision/text/model/chunk parameters determine cache identity. Verify the configured embedding artifact before CLI inference.
- At most eight batches, two story and two background passages per batch, sixteen topic query embeddings in one bounded request.
- Generation may use spoiler-bearing evidence internally; draft output is not automatically served to users. Existing published UI spoiler gates remain.
- Cosine scores rank passages; they are not evidence of answer correctness.
- Default CLI evidence mode becomes rag; section mode remains an explicit comparison baseline. Direct coordinator callers retain the existing section default.
- No publication database writes. Frontend remains unchanged.

## Tasks

- [x] Extract complete evidence pools from the existing adapter, preserving existing section-mode behavior and provenance checks.
- [x] Implement retrieve_draft_evidence(client, source, store, model, max_batches) returning batches plus auditable query/window/selection trace. Ingest and load only the exact snapshot. Map window scores to complete sentence groups, exclude previously selected groups, and fail closed on unclassified evidence.
- [x] Add coordinator evidence_loader inside its overall deadline; save retrieval trace before generation. Add CLI --evidence-mode and --evidence-store; verify embedding digest in rag mode.
- [x] Test persistent cache reuse, changed revision, story/background isolation, ranking, complete source offsets, deduplication, budgets and failure before generation. Use deterministic transport fixtures for contracts, not semantic-quality claims.
- [x] Run full backend checks and a bounded real local retrieval smoke test. Preserve trace and timing, then optionally run one real generator/critic batch to prove composition.
- [x] Write lesson 40 with actual outputs, explain retrieval vs generation vs publication, and update progress. Record limitations and next visible preparation/review workflow.

## Completion evidence

574 backend checks passed. Cold v1 retrieval 3.8s, cached v1 0.47s, final filtered v2 cache run 0.43s. The v1 end-to-end smoke retained two fact drafts and rejected both production-trivia questions in 61.29s. Final v2 first batch matches exactly; preserved v1 labels on historical artifacts. Reviewed collections and frontend unchanged. Next increment separates generation branches before visible preparation/review.
