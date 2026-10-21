# Learner-owned AI pipeline — pairing plan

**Goal:** Let the learner implement and explain the LLM/RAG path end to end, with assistant-built application infrastructure.

**Architecture:** Direct local Ollama calls first, followed by inspectable retrieval and grounded generation. Keep catalog and evidence indexes separate. Introduce frameworks only after the learner can explain the underlying data flow. Work inline together; do not delegate the learner's code or implement multiple stages ahead of them.

**Tech stack:** Existing Python 3.12, HTTPX, pytest, FastAPI; local Ollama; persistent Chroma and lexical retrieval at the storage milestone. No new infrastructure is installed by this plan.

## Ownership and checkpoints

Latest user instruction (2026-10-09) overrides earlier validation assignments: the learner focuses on API calls and main AI business logic. The assistant owns input/output validation, malformed-response handling, permission checks, guardrail enforcement, tests, and supporting infrastructure. Keep those concerns explainable, but do not require the learner to finish routine checks before proceeding. Learner-owned retrieval, prompt design, and agent decisions remain hands-on exercises.

| Stage | Learner implements | Assistant supplies | Verification before moving on |
|---|---|---|---|
| 1. Local inference | `chat_once` request/response handling; cosine input guards | Test transport, runnable local script, lesson 07 | 11 vector + 7 chat checks and an actual local reply |
| 2. Embeddings | Text-to-vector request, validation, reusable movie input text | Model setup guidance, typed records, version/hash persistence plumbing | Shape/finite/zero checks; query and corpus use identical model |
| 3. Retrieval | Chunking and top-k scoring over a small inspectable corpus | Attributed/synthetic fixtures, storage interfaces, hard-filter support | Labeled relevant passage IDs, Recall@k and no filter violations |
| 4. Grounded generation | Evidence prompt construction, missing-evidence behavior, structured answer parsing | Source records, bounded model client, response schema, UI rendering | Citation IDs exist; missing evidence abstains; human support checks |
| 5. End-to-end movie RAG | Connect ingestion, retrieval, prompt and generation in one pipeline | Source connectors, permissions, jobs, FastAPI routes, frontend integration | Selected movie/spoiler scope enforced before prompting; failure recovery |
| 6. Tools and agents | Typed tool decisions, orchestrator state, stop/repair rules, parallel branches | Read-only scoped tools, trace plumbing, UI run status | Injection/tool misuse fixtures, budget checks, single-vs-parallel comparison |
| 7. Evaluation | Label cases, choose metrics, inspect failures, document trade-offs | CI runner and report scaffolding | Development/held-out separation and measured claims only |

This is a curriculum map, not permission to finish the AI implementation on the learner's behalf. Each stage gets its own bounded implementation plan and exercise before integration. Lesson 07 contains the concrete first-step interface, request shape, examples, commands, and tests; later stages are not started now.

## Current stage

- [x] Review existing cosine code: five ordinary cases pass; six guards remain.
- [x] Check the running Ollama service and installed models without generating learner code.
- [x] Verify current official chat, embedding, and model-list API documentation.
- [x] Provide `chat_once` stub, seven fake-transport checks, local smoke script, and lesson 07.
- [x] Learner completes cosine guards and first chat call.
- [x] Review implementation and questions; run focused checks and a real local request.
- [ ] Extend application client error handling and prepare the embedding stage while preserving learner ownership.

## Boundaries

Use only local inference for the first call; do not download models or call remote inference automatically. Future evidence keeps provenance, movie identity, spoiler classification, and ownership. Retrieved text is untrusted data; model prompts cannot authorize tools. No shell/deletion/automatic posting tools. Safety evaluations report their tested scope; they do not claim universal prompt-injection protection.
