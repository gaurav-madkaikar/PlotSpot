# Pairing slice — embeddings and cosine similarity

## What we are building

Semantic search finds films by meaning, such as “a thoughtful movie about communicating with aliens.” Title/cast matching cannot answer that request reliably. We will embed a movie description and the query with the same local Ollama embedding model, then rank eligible movie IDs by vector similarity.

An embedding is a list of numbers produced by a model. Related texts tend to have nearby vectors. Individual coordinates are not human-readable labels such as “space” or “comedy.” This exercise uses small invented vectors to learn the comparison; they are not actual movie embeddings.

The initial learning check uses the ten fixture films. The planned semantic catalog will expand to 200 validated films. Search will disclose its catalog coverage; it will not claim to search all TMDB movies by meaning.

## Your coding slice

Implement only `cosine_similarity(left, right)` in `backend/src/movie_companion/vector_math.py`. No new dependency or API call is needed.

Cosine similarity = dot product / (length of left × length of right).

- Dot product: multiply corresponding coordinates and sum the products.
- Vector length: square each coordinate, sum those squares, then take the square root.
- Reject empty vectors, unequal lengths, and non-finite coordinates with `ValueError`.
- Return `0.0` if either vector has zero length. This avoids division by zero; later ingestion should also detect useless zero embeddings.
- Otherwise return the similarity. Opposite vectors can score negatively; do not clamp everything to 0–1.

For `[1, 1]` and `[1, 0]`, the dot product is 1 and the lengths are √2 and 1. Similarity is approximately 0.7071. Multiplying a vector by a positive constant changes its length but preserves its direction, so `[1, 2]` and `[3, 6]` score 1.

Hints: `zip`, `sum`, and the standard-library `math.sqrt` and `math.isfinite` are enough. Check lengths before using `zip`, because `zip` silently stops at the shorter list. Floating-point assertions use `pytest.approx` because calculations can have tiny rounding differences.

From `backend`, run:

```sh
.venv/bin/pytest tests/test_vector_math.py -q
```

The 11 checks intentionally fail until you implement the function. The stub is not connected to the application, so the existing webpage continues to work. The full backend suite includes these checks and will also be red during this exercise.

## What I will extend after your implementation

Ownership update: you now want to implement the LLM/RAG path yourself with guidance. The steps below describe the feature sequence; the AI functions will be your exercises, while I supply infrastructure and integration. See lesson 07 for the first local model call. Your current cosine formula passes the five ordinary cases; input validation and zero-vector behavior still need the three guards explained there.

1. Review the vector math and explain its behavior.
2. Verify the local Ollama service/model and add a bounded embedding client using its documented API. Handle unavailability and invalid embeddings explicitly.
3. Build versioned movie embedding records containing the movie ID, embedding model, input text hash, and vector. Reuse unchanged embeddings rather than recomputing them per search.
4. Filter known movies by genre/runtime/language before ranking. Return movie records backed by real IDs, with explicit catalog coverage.
5. Add an explicit semantic-search mode to the UI, preserving ordinary title/cast search.
6. Introduce labeled meaning-based queries before measuring retrieval. Report top-k identity recovery, hard-filter violations, coverage, and latency separately from typo results.

This math exercise is the first step, not a completed semantic search or RAG system. RAG will later retrieve attributed news/story passages to ground facts and discussions; movie discovery uses a separate catalog index.

## Concepts to explain after review

1. Why use the same embedding model for movies and queries?
2. Why can two different-length vectors have cosine similarity 1?
3. Why does a high similarity score not prove that a film satisfies a runtime limit?
4. What should happen when Ollama is offline?
5. How is a stored embedding different from the HTTP response cache?

## Completed review and answers — 2026-10-09

Your cosine implementation passes all 11 checks. You added the nonempty/equal-length/finite-coordinate guards and zero-vector behavior while retaining the correct dot product and norm formula. These are small-vector functional checks; they do not measure movie recommendation quality or all extreme floating-point values.

1. **Same embedding model:** corpus and query vectors must use the same coordinate space. Equal dimensions alone do not make different models' coordinates comparable. Changing model/version or text construction can require rebuilding the index.
2. **Similarity 1 despite different magnitudes:** cosine compares direction. Scaling every coordinate by a positive constant scales the dot product and norm together, so the ratio remains 1. Negative scaling reverses direction.
3. **Similarity doesn't enforce runtime:** a vector represents text relationships, not an authorization or filtering decision. The backend must apply explicit runtime/genre/language constraints independently before ranking eligible films.
4. **Ollama offline:** show a recoverable model-unavailable state. Ordinary title/cast search can remain available. Do not fabricate a semantic result or silently claim keyword results are meaning-based search.
5. **Embeddings versus HTTP cache:** a versioned embedding index supports repeated retrieval and is rebuilt when its model/input changes. The HTTP response cache temporarily reuses provider responses and expires by TTL. They have different identities, lifetimes, and invalidation rules.
