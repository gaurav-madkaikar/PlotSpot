# Movie RAG Evaluation Implementation Plan

**Goal:** Measure retrieval and generation separately using the real learner pipeline and frozen movie evidence.

**Architecture:** Prepare a local SourceDocument/catalogue once; label development questions against stable chunk IDs; trace the existing pipeline via an optional observer; grade deterministic expectations and preserve a compact local-model report.

**Tech Stack:** Existing Python, Pydantic, HTTPX, Chroma, pytest and Ollama. Inline execution follows the existing pairing preference.

## Constraints

- Preserve learner embedding/retrieval/generation decisions. Assistant owns runner, validation, tests and explanation.
- Fixed Interstellar mapping, unknown spoiler status, explicit whole-source permission in this local developer command.
- At most 20 cases; 180 seconds per case; no retries/downloads, fixed loopback inference.
- Frozen source text and catalogue under ignored `data/private/movie-rag`; separate vectors under `data/chroma/eval`.
- Never overwrite existing `evals/movie-rag/cases.json` during preparation. Verify source snapshot before inference.
- Only development results; human support review pending, unknown metrics excluded from denominators.

## Tasks

- [x] Add optional `on_retrieved` callback to `movie_qa_learning.answer_movie_question`, default None; call it after retrieval without changing hits. Extend the existing mock-HTTP pipeline test to assert its actual hit ID.
- [x] Create `movie_rag_eval.py`: strict case/dataset models, maximum lengths, answered/abstention consistency, duplicate/unknown IDs and snapshot checks. Grade hit@3, annotated-ID recall, status/phrase/citation checks with explicit null retrieval metrics on abstention cases. Tests include hit/miss, valid abstention, foreign citation, unknown labels and fingerprint mismatch.
- [x] Create `scripts/evaluate_movie_rag.py`: `--prepare-source` freezes public source and writes chunk catalogue plus two starter labels without overwriting; default mode validates frozen inputs, ingests, runs actual pipeline sequentially, records scores/IDs and metadata, writes report and exits nonzero on failures.
- [x] Run all backend tests. Prepare the public source with consent already provided for this milestone, run the two starter cases on local Ollama, preserve every failure without prompt tuning.
- [x] Save lesson 16 with a worked label, field/metric explanations and the learner's instrument question assignment; record actual test/eval results in PROGRESS.

## Outcome

217 backend checks pass. Frozen public source prepared; local-model two-case baseline passed 2/2 with zero generation errors and supporting hit 1/1 labelled answerable case. Report retains all selected IDs/scores and model/source/prompt metadata. No frontend behavior changed. Human support review and learner instrument label remain next; no broad accuracy or security inference is made.
