# Grounded Generation Implementation Plan

**Goal:** Teach evidence-based prompting through one learner-owned function, using the completed retrieval and local chat helpers.

**Architecture:** Following stage 4 of the approved learner-owned pipeline, serialize already-filtered hits as JSON, build a prompt, call the existing local chat helper once, and validate the structured reply. Empty evidence abstains without a model call. This slice has no app routes, new framework, persistence, tools, or automatic retries.

**Tech Stack:** Existing Python 3.12, HTTPX, pytest, Ollama.

## Constraints and ownership

The learner writes `build_grounded_prompt(question: str, evidence_json: str) -> str`. The assistant handles evidence limits, JSON serialization, response validation, citation checks, tests, and the script. The response has exactly `status`, `answer`, and `citation_ids`; status is `answered` or `insufficient_evidence`. An answered response needs at least one supplied passage ID. An abstention has no IDs and displays a fixed explanation. Citation membership is not semantic entailment verification. Evidence is untrusted; no model reply can execute actions. Keep the learner function unfinished until the learner codes it.

## Task 1 — prompt exercise and validated generation boundary

Files: create `backend/src/movie_companion/grounding_learning.py`, `backend/tests/test_grounding_learning.py`.

- [ ] Provide the prompt stub. The learner's prompt must include the question, evidence JSON, JSON output fields/statuses, evidence-only answering, instructions to treat evidence as untrusted data, and insufficient-evidence behavior. Tests check the output contract and inclusion, not semantic quality.
- [ ] Implement `answer_from_hits(client, *, model, question, hits) -> GroundedAnswer`: validate bounded text and up to six unique passage IDs; serialize text/source/ID without vectors; abstain on empty hits; call `chat_once` once; parse JSON and enforce field types, status, and citation membership.
- [ ] Test prompt inclusion and JSON contract against the unfinished stub. Separately monkeypatch the builder to verify malformed replies, citation failures, abstention, and propagated HTTP failures without depending on learner code.

## Task 2 — end-to-end teaching script and explanation

Files: create `backend/scripts/try_local_grounded_answer.py`, `docs/learning/10-grounded-generation.md`; update `docs/learning/PROGRESS.md`.

- [ ] Reuse explicitly fictional notes from the retrieval script. Embed notes and query, retrieve movie-scoped spoiler-filtered hits, pass to generation with `llama3.2:3b`, print answer/status and resolved source IDs. No web or external inference.
- [ ] Explain retrieval versus generation, JSON serialization, asynchronous composition, unsupported-question abstention, and injection limitations. Include Python string patterns without completing the learner function.
- [ ] Verify the exact intentional prompt-test failures, all other backend checks, and Python compilation. Do not run local inference through the unfinished prompt or claim answer quality.

## Subsequent learner review

Preparation completed: the prompt stub, validated wrapper, tests, script, and lesson are present. Verification produced exactly two expected prompt failures and 17 passing boundary checks; all 111 existing backend cases pass, and new Python files compile. The learner prompt and subsequent model review remain pending.

After implementation, review prompt semantics, run tests and the real local example, inspect claim support manually, and save question answers/results in lesson 10. Do not equate prompt wording or syntactically valid citations with a safety or accuracy guarantee.
