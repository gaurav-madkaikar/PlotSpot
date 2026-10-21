# 28. Preparing a larger catalog safely

## What is stored

Each movie keeps its TMDB ID, title, alternative titles, cast, genres, keywords, synopsis, poster URL and existing detail metadata. Preparation reads TMDB metadata and embeds it locally. It does not fetch scripts or prepare quiz/facts evidence for all 1500 films.

TMDB keyword and alternative-title data are requested alongside credits using `append_to_response`. Genre discovery is sampled round-robin to retain a mix of films. Previous canonical IDs are seeded so catalog expansion preserves the evaluation targets where upstream metadata remains available.

## How resumption works

The metadata checkpoint records the configuration, discovered IDs and validated complete movies. Successful batches are saved even if another record fails. A restart fetches only unfinished records. Missing/empty records are replaced from a larger candidate pool; transient failures have bounded backoff.

Embeddings have a separate checkpoint keyed by a hash of the model and exact embedding text. Unchanged descriptions reuse existing vectors. Each completed batch is saved, so an interrupted embedding run resumes without repeating all model calls. Changing the model/template invalidates reuse.

Checkpoint files contain public movie metadata and vectors, not the TMDB token. The token remains in local configuration. Publishing is explicit and separate from the user search request.

## Why atomic publication matters

The current catalog stays readable during preparation. Only a complete validated index is written to a temporary file and renamed into place. The previous published snapshot is retained as `semantic-catalog.previous.json`. An import failure cannot publish a half-finished collection.

The new metadata-v2 fingerprint includes keywords and alternative titles. Older metadata-v1 snapshots are readable with their original fingerprint rules, but cannot contain unhashed new fields. Vector counts, values, dimensions and canonical identity manifests are checked before publication.

## Commands

From the project root:

```sh
backend/.venv/bin/python backend/scripts/prepare_semantic_catalog.py --refresh --count 1500 --metadata-only
backend/.venv/bin/python backend/scripts/prepare_semantic_catalog.py --refresh --count 1500
```

The first command fetches/checkpoints metadata. The second resumes metadata and prepares/publishes embeddings. Without `--refresh`, the script retains the existing index without network or model calls. Checkpoints live under `data/private/prepare-1500/`. A changed preparation configuration requires a separate checkpoint path.

## Limits

This remains a curated local snapshot with English-oriented semantic search. Some provider keywords are missing or imperfect. More records improve coverage, but keyword quality, candidate retrieval, reranking and evaluation still determine recommendation quality.

## This publication

Published 1,500 unique TMDB movies with 768-dimensional local embeddings. Keywords are available for 1,421 movies and alternative titles for 1,449. All 75 live browse pages were checked for duplicates and page size. The snapshot fingerprint is `a356db695a2499db83361ac57093e8c75546159800b39b74f8f66012b044f5c7`. This establishes ingestion integrity, not search relevance.

To roll back, copy `data/private/semantic-catalog.previous.json` to a temporary sibling of `data/private/semantic-catalog.json`, validate it with `read_index`, then atomically replace the published file. The app detects the completed file replacement on the next request. The preserved `.cache/eval-snapshots/catalog-200.json` is the original evaluation snapshot; the metadata/vectors remain local and ignored by Git.
