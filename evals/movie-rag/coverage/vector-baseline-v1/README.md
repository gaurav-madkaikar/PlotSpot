# Frozen discussion baseline

These two modules preserve the vector-only discussion pipeline and its original
full-passage-ID generation contract from before the 12 October retrieval work.
They are loaded only by `backend/scripts/evaluate_registered_movie_rag.py
--compare`. Application code never imports them.

The evaluator explicitly binds the archived pipeline to the archived grounding
module. Embedding, cosine retrieval and local HTTP helpers remain shared; this
is a frozen pipeline/prompt comparison, not a snapshot of every dependency.
Reports record both archive hashes, current policies, model digests, source
revision, chunk settings and dataset fingerprint. A fixture checks that the
baseline keeps its original prompt/schema and vector ordering.

Both arms use the same frozen passages and labels, run sequentially, and
alternate execution order per case. Warm caches and local model state affect
timings. Do not present this as a production latency benchmark, a pure retrieval
ablation or a multi-agent comparison: retrieval and generation contracts both
change in the candidate.
