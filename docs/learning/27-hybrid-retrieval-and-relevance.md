# 27. Hybrid retrieval and relevance checking

## The new data flow

Title/cast matches and clear typo corrections remain deterministic. Explicit UI filters stay strict. A bare genre request such as `romance` uses genre metadata. A description such as `a quirky hotel adventure` treats Adventure as a preference, allowing a Comedy/Drama film to compete.

For descriptions, two independent tasks run together:

1. BM25 finds literal evidence in titles, alternative titles, genres, keywords and synopses. Rare words contribute more than common ones.
2. Ollama embeds the query; cosine similarity ranks eligible movie vectors by meaning.

`hybrid_retrieval.py` merges bounded candidate lists, deduplicates canonical IDs, and sends their metadata to a separate relevance checker. Missing literal words cannot eliminate a semantic candidate before this stage. The final configuration takes 24 semantic and 8 lexical candidates. This bounded pool can still miss a relevant film; a relevance checker cannot recover a film it never receives.

The acceptance score is an ordinal grade, not a similarity score or probability. Grade 2 means clearly relevant. Development replay at grades 1, 2 and 3 tied on our incomplete labelled hit/empty metrics, so it does not prove an optimal threshold. We retain the predeclared grade-2 rule and record this limitation in the calibration report.

## Why use a second model call?

An embedding compares vectors created separately. The relevance checker reads the query and candidate descriptions together. This can distinguish a film about superheroes from a documentary about a famous person called a hero. It costs more time and can still make mistakes, so we evaluate it rather than assuming extra AI calls improve quality.

Hugging Face model downloads are blocked by the local Cisco security policy. We use an already-installed Ollama model instead of bypassing that block. The small Llama model and stronger Qwen model are compared on development queries. Versioned reports record the results; do not treat either model as an infallible judge.

## Safe structured output

The model returns an array of ratings in supplied order: 0 unrelated, 1 weak, 2 relevant, 3 strong. It cannot return a title, URL, file path, executable code or tool call. Strict validation checks types, range and array length. The application maps each position to its original trusted movie ID.

This avoids a practical failure found during development: a small model could produce valid JSON containing incomplete or invented movie IDs. Schema validation alone would not catch all those identity errors without an allowlist.

A valid rating can still be semantically wrong or aligned incorrectly. The evaluation set checks retrieval quality separately from structural output checks. Prompt-injection tests do not prove perfect resistance; the absence of tools prevents the checker from executing malicious actions.

## Filters and failure handling

Explicit genre, language and runtime limits are applied before candidate retrieval. Genre exclusions extracted from queries remain strict. Positive descriptive genre wording is passed to relevance checking. The checker cannot bypass the prefiltered candidate pool.

Timeouts, invalid ratings and unavailable Ollama produce a recoverable error instead of displaying unchecked nearest neighbors. One AI workload per service runs at a time; identical searches share the same task. A viewer disconnecting cannot cancel a search another viewer awaits. This is a bounded single-machine deployment, not a horizontally scaled production service.

## Caches and traces

Ranked results are cached for five minutes with a bound of 64 entries. Keys include the catalog fingerprint, retrieval version, relevance model, acceptance setting, query and eligible IDs. Pagination slices the cached ranking instead of calling the model again. Existing query embeddings have their own bounded cache.

The parsed catalog snapshot is reused until its file timestamp/size changes. Atomic publication makes a completed new snapshot visible together. Search logs include a query hash, catalog fingerprint, candidate count, match type, result count and latency; raw query text is omitted. Evaluation reports include candidate IDs and ratings for diagnosis.

## Your next hands-on piece

Read `search_reranker.py`, particularly the request payload and `_score_batch`. Trace one query through `catalog_search.py` and `hybrid_retrieval.py`. Then add a labelled query to a new evaluation file before running it, predict which stage could fail, and inspect the trace. Avoid changing the held-out validation file to fit model outputs.

Browsing covers 75 pages of 20 films after the 1,500-record publication. Semantic results contain at most 32 checked candidates; they are a recommendation shortlist, not exhaustive matching over every catalog entry.
