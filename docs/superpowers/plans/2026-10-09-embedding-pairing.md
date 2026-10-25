# Embedding request pairing plan

**Goal:** The learner writes a local embedding API call and can explain its vectors and validation.

**Architecture:** A disconnected pure API adapter accepts an injected HTTPX client and sends a batch to `/api/embed`. A supplied teaching script compares results using the learner's cosine helper. Store/retrieve/answer integration remains a subsequent checkpoint.

**Tech stack:** Existing Python 3.12, HTTPX, pytest; local Ollama `nomic-embed-text:v1.5` for the optional real experiment.

**Ownership:** Preserve learner ownership of `embed_texts`. Do not download the model automatically. Do not implement retrieval or introduce LangChain/Chroma in this slice.

- [x] Verify official Ollama embedding contract and Nomic task prefixes.
- [x] Inspect installed models; provide the official model download command in lesson 08.
- [x] Provide `backend/src/movie_companion/embedding_learning.py` with the typed learner stub.
- [x] Provide 19 fake-transport checks in `backend/tests/test_embedding_learning.py` with malformed shape, coordinate, cardinality, and input cases.
- [x] Provide `backend/scripts/try_local_embeddings.py` with a small synthetic comparison experiment, using the same model for documents and query.
- [x] Write lesson 08 with request/response examples, Python validation patterns, commands, and review questions.
- [x] Learner implements the API request and parsing; assistant finishes validation under updated ownership. All 19 focused checks pass.
- [x] Review it, run a real comparison with the user-installed model, and record answers. Retrieval remains the next learner-owned slice.

Acceptance: validated nonempty/equal-dimensional/finite/nonzero vectors in input order; HTTP failures preserved; no fabricated semantic results; existing app behavior unchanged. Unit checks verify contract handling, while the real experiment only demonstrates local inference and relative scores.
