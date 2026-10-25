# Evidence Chunking Pairing Plan

**Goal:** Teach the learner how a source becomes overlapping evidence windows before persistent indexing.

**Architecture:** A learner-owned character-window loop returns text and source offsets. An assistant-owned wrapper validates input limits and output coverage. An authored fictional article and offline tests demonstrate boundary behavior. Token-aware/paragraph-aware chunking and persistent Chroma storage follow after this slice; do not implement the learner's loop or storage ahead of them.

**Tech Stack:** Existing Python 3.12 and pytest. No new packages or model downloads.

## Task 1 — bounded chunking exercise

- [ ] Create `backend/src/movie_companion/chunking_learning.py`: frozen `TextChunk(start, end, text)`, learner `split_windows(text, *, max_chars, overlap_chars)`, and assistant `chunk_text` boundary. Validate string length up to 100000, integer chunk size 1..2000, integer overlap 0..size-1. Empty/blank text returns no chunks. Preserve original text and character offsets; do not normalize or trim.
- [ ] Check returned spans match source slices, full source coverage, bounded window widths and requested overlap. Stop at source end; do not duplicate a trailing overlap-only chunk.
- [ ] Create focused tests for short input, overlap, exact boundaries, no overlap and Unicode plus invalid inputs and malformed returned spans. Ranking/model helpers remain unchanged.

## Task 2 — explanation and demonstration

- [ ] Create `backend/scripts/try_chunking.py` with a clearly fictional production article and visible spans; no Ollama needed.
- [ ] Create lesson 12 with sliding-window examples, character/token distinction, provenance, overlap tradeoffs, and the connection to ingestion/storage. Leave the complete algorithm to the learner.
- [ ] Verify expected starter failures separately from boundary tests and all existing tests. Record the learner-owned slice in progress.

This is an approved curriculum step, not a new application feature. The assistant may correct the existing prompt as explicitly requested; its actual evaluation results are recorded separately. No claim of guaranteed grounding quality follows from that correction.
