# Retrieval for fact and quiz drafts

This increment implements the approved fetch/index/retrieve/generate/review flow using existing validated Wikipedia snapshots. Scripts require a later adapter with released-film versus draft provenance. No new source URLs or publication rights are introduced.

Three alternatives are direct article context (simple, wastes context), section-order selection (current inspectable baseline), and cached embeddings with purpose-filtered topic retrieval (selected, reuses existing local components and makes selection traceable). Retrieval uses fixed application-owned topics, not an unrestricted model planner.

Persistent section-aware windows are embedded once for the exact source fingerprint. Topic query vectors rank only matching story/background windows from that snapshot. Complete sentence groups are scored against overlapping windows and selected without repetition; references and offsets are revalidated before generation. Retrieval scores, selected IDs, topics and source cache identity are saved with draft checkpoints. Eight batches and the existing overall deadline bound inference.

The existing generator and critic remain unchanged. Failure retains completed draft checkpoints; insufficient evidence yields incomplete output rather than invented questions. Retrieval success does not approve publication or prove semantic support. The reviewed app collections and UI are unchanged. Validate contracts with isolated transport fixtures and run bounded real Ollama smoke tests; these are not a representative semantic benchmark.
