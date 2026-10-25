# In-memory evidence retrieval pairing slice

Date: 2026-10-09. Implements the next retrieval stage of the approved learner-owned AI pipeline; scoped to teaching helpers, not application routes.

## Ownership and outcome

Learner: implement `rank_passages`, calculating cosine scores, deterministic ordering, and top-k selection while retaining evidence records.

Assistant: provide typed records, vector/model/identity checks, movie and spoiler filtering, focused tests, fictional local example, explanations, and review. Do not fill in the learner's ranking function.

## Components

- `retrieval_learning.py`: passage/hit dataclasses, learner stub, assistant-owned boundary.
- `test_retrieval_learning.py`: ranking, tie, negative score, input preservation, scope, and invalid-vector checks.
- `try_local_retrieval.py`: embed pre-split authored fictional notes and question using the completed helper, retrieve evidence, print IDs/scores/text.
- Lesson 09: beginner Python patterns, worked vectors, commands, RAG placement, limitations, review questions.

## Verification and follow-up

At preparation, verify five expected ranking failures and eleven passing boundary cases; verify existing backend tests independently and compile new Python files. No generated-answer or retrieval-quality result should be claimed from stub preparation. After the learner finishes, run the focused cases, review ranking, run the real local example, and record findings/answers. Chunking, persistent indexing, grounded prompts, and application integration remain subsequent slices.
