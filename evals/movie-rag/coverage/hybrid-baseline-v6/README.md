# Frozen Lesson 58 discussion baseline

These three source files preserve the hybrid/excerpt pipeline before complete
sentence recovery and the separate support reviewer. They are developer-only
comparison artifacts and are never imported by the application.

`evaluate_registered_movie_rag.py --compare-current` loads these archived
pipeline, retriever and grounding modules, then reconnects their references.
The baseline uses one query embedding and one generator call; no new context or
semantic reviewer stage is included.

Shared validation, embedding, sentence parsing and passage data helpers remain
those of the current project. This is a frozen three-module pipeline baseline,
not a fully vendored environment. Both arms use the same source revision,
original chunks/embeddings, labels and generator model. Newly attached optional
locations are ignored by the archived baseline. Reports retain artifact hashes
and installed model digests. Reproduction also requires the private frozen
source snapshots and compatible local dependencies.
