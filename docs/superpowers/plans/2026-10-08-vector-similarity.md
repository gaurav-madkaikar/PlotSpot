# Vector Similarity Pairing Plan

**Goal:** Teach and verify the vector comparison needed for the approved semantic-catalog milestone.

**Architecture:** A dependency-free pure function compares embedding vectors. It remains disconnected from the running application until the learner's implementation is reviewed. This plan covers only that pairing slice; Ollama ingestion and UI integration follow in the next bounded plan.

**Tech stack:** Existing Python 3.12 and pytest; standard-library math.

**Working constraint:** The learner implements the function. Do not provide its complete solution or implement their slice silently. Keep the existing UI usable.

- [x] Create `backend/src/movie_companion/vector_math.py` with `cosine_similarity(left: list[float], right: list[float]) -> float` and an explicit exercise stub.
- [x] Add numeric checks in `backend/tests/test_vector_math.py` for identical direction, scaling, orthogonality, opposition, partial alignment, and zero vectors; require `ValueError` for empty/mismatched/non-finite vectors.
- [x] Explain dot product, magnitude, edge cases, expected failures, and the eventual app connection in `docs/learning/05-embeddings-and-similarity.md`.
- [ ] Learner implements cosine similarity and runs the 11 focused checks.
- [ ] Review the implementation, answer the learning questions, and run the complete backend suite. Then plan the Ollama embedding integration against current official API documentation.

Acceptance: all focused checks pass after the learner's implementation; no application behavior changes in this preparatory slice. The existing approved project design specifies the eventual 200-film catalog and local Ollama embeddings; this exercise does not claim to deliver them.
