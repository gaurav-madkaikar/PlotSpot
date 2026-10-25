# Frozen Lesson 59 support baseline

Four archived modules preserve the sentence-context builder, generator boundary,
local reviewer and question pipeline before Lesson 60 identity/relation changes.
They are comparison-only and are never imported by the application.

`evaluate_registered_movie_rag.py --compare-support` reconnects these archived
functions. The old reviewer returns verdict/reason only and uses a 512-token
output cap. It adds no mandatory identity sentence. Both arms keep the same
registered article revision, original passage text/vectors, labels, retriever,
embedding model and generator/reviewer model digests.

Shared source, data classes, validators, embedding and sentence parsing helpers
remain current. SupportOption is the current shared type, with its new flag
false for old baseline options. This is a four-module baseline, not a vendored
runtime. It requires private frozen source snapshots and local dependencies.
Top-three retrieval and expanded generation IDs are separately observed in both
arms so citation checks do not penalize authorized baseline context expansion.
