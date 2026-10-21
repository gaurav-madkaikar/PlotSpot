# Hybrid movie search and expanded catalog

User-approved scope: replace brittle description gates with hybrid retrieval and relevance checking, compare on the current 200-film snapshot, then expand to up to 1500 films with safe ingestion. Keep plain Python AI modules and learning notes.

- [x] Add local structured Ollama relevance checking using installed models, validated scores, bounded candidates, cached result pages, and safe failures. Combine lexical and Ollama vector candidates; preserve title/cast/typo precedence and explicit filters.
- [x] Distinguish query-derived genre preferences from strict genre-only requests; retain exclusions. Evaluate and calibrate acceptance on development labels, recording model/version/config and tradeoffs. Add separate labelled validation queries before using them for assessment.
- [x] Extend saved metadata with keywords/alternative titles and compatible versioned snapshots. Implement bounded 1500-record importer with retries, checkpointed metadata and embeddings, atomic publication and preserved baseline snapshot.
- [x] Run meaningful mocked integration/failure tests, existing checks, real 200-film evaluation, full import, expanded-catalog evaluation and live browser verification.
- [x] Document results, known limits, rollback/reproduction commands, and AI learning examples. No claim of universal production accuracy from development results.

Files: hybrid_retrieval.py and search_reranker.py own retrieval/scoring; catalog_search.py orchestrates identity/filter/paging; semantic_search.py owns local query embeddings and bounded cache; catalog_import.py owns provider sampling; prepare_semantic_catalog.py owns checkpoints/publication. Evaluation scripts keep baseline reports separate.

Environment decision: Hugging Face downloads are blocked by Cisco security controls. Compare installed models; select qwen3.5:9b rather than downloading/bypassing blocks. Candidate IDs and scores are strictly validated.

Completed with 1,500 published records, 361 backend tests, frontend build, 35 browser cases across initial run plus timeout retries, live search/pagination verification, development/calibration and separate frozen-query validation reports. Remaining relevance and latency limits are documented; no production-ready claim.
