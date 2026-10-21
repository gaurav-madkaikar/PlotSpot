# Bounded movie research implementation plan

**Goal:** Run independent source research concurrently with partial-result
handling and compare identical sequential/parallel preparation inspections.

**Architecture:** Typed purpose-specific source loaders feed an asyncio
coordinator; model retrieval/generation/review consumes the result serially.
The CLI writes a nonpublishing report and compares immutable cached inputs.

**Tech stack:** Python 3.12, asyncio, existing HTTPX/source adapters and Ollama.

**Constraints:** Two branches; one story and at most two background sources;
branch deadline 0.01–60 seconds and workflow deadline 0.01–120 seconds. Existing
model policies and saved banks stay unchanged. No consumer drafts or new UI.
Execute inline under existing authorization; no commits or subagents.

- [x] Add `movie_research.py`: typed source results, fixed source loaders,
  movie/URL/purpose validation, parallel/sequential coordination, partial
  expected failures, separate deadlines and cancellation/join semantics.
  Test overlapping starts with events, deterministic order, failed/ambiguous
  sources, one failed article, deadlines and propagation of caller cancellation.
- [x] Add `research_preparation.py`: consume validated research through existing
  story and background RAG/generator/critic modules. Keep model work serial;
  retain a successful branch if the other fails. Test origin preservation,
  absence of calls for missing evidence and no publication permissions.
- [x] Add `inspect_movie_research.py` and fixed operational evaluation cases.
  Compare identical cached snapshots with alternating execution order; record
  module/model/source hashes, source acquisition timings, generation timings
  and automated necessary checks. Avoid historical report overwrite.
- [x] Run deterministic checks and a real Ollama Arrival comparison; inspect
  generated content and retained failures. Check code hashes and bank/script
  preservation. Keep latency and quality limitations explicit.
- [x] Write Lesson 61, update checklist/README/progress, record results and
  reproduction commands. Self-review docs against actual delivered scope.
