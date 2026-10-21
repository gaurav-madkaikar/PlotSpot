# Screenplay ingestion

Approved scope: read IMSDb scripts for story/quiz/discussion RAG, preserve movie and draft identity; assistant performs implementation and validation. Execute inline without commits.

Design: reviewed fixed mappings for Inception, The Matrix and Interstellar. Extract only the first preformatted screenplay, normalize lines, validate title/author/version markers, preserve opening material and scenes. Persist the normalized snapshot privately. Group whole scenes into bounded SourceDocuments and use existing Chroma storage with nomic embeddings. Fetch once; explicit refresh creates a new content fingerprint. Batch embeddings across missing documents, load only the selected revision. Require spoiler consent before retrieval. Treat every script as unverified against the released film, including shooting scripts. No automatic publication or script-only scored quiz answers.

- [x] Add adapter/cache with bounds, identity checks, exact normalized-text spans and scene grouping.
- [x] Add batched indexing and movie/revision-scoped retrieval with a local CLI.
- [x] Test malformed sources, cached data tampering, scene boundaries, indexing reuse, consent and retrieval.
- [x] Run real three-source parsing and local Ollama retrieval/cache verification; report metadata without screenplay excerpts.
- [x] Document usage, learning concepts and the remaining corroboration integration.

Files: backend/src/movie_companion/screenplay_source.py (fetch, parse, cache); screenplay_retrieval.py (index, retrieve); backend/scripts/ingest_movie_script.py (local command); tests/test_screenplay_ingestion.py (synthetic fixtures); docs/learning/43-screenplay-ingestion.md.

Validation: existing external-source tests remain compatible; run complete backend tests after new tests pass. Retrieval similarity is a ranking score, not factual verification. The current proposal/critic contracts have one evidence alias per item and need an explicit additional cross-source verification step before scripts can enter released-film quizzes.
