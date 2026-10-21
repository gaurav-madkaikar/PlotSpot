# Real-film fact evaluation implementation plan

> Execute inline under existing user authorization. No delegation, publication or changes to the frozen writer/critic policy.

**Goal:** Measure current fact verification on fresh real-film evidence and inspect actual local generation across six films.

**Architecture:** Reuse the labelled critic evaluator. A separate bounded evaluation module verifies short excerpts against revision-pinned private snapshots, records dataset/source/model/policy hashes, and inspects the existing article writer without granting publication permissions. Labels are assistant-authored development expectations, frozen before inference; this is not an independent accuracy benchmark or full RAG retrieval evaluation.

**Tech stack:** Python, Pydantic, existing httpx/Ollama clients and pytest.

## Constraints

- Preserve all ten saved collections and current generation qualifications.
- Use fixed local qwen3.5:9b; no tools supplied to the model, no automatic retries or publication.
- Keep malformed responses, deadline failures and uncompleted films in denominators.
- Preserve report files; a rerun needs a distinct output path.
- Source passages must match registered movie/revision/section/span and pinned snapshot hashes.

## Tasks

- [x] Freeze eighteen labelled fact cases across six movies, with new supporting excerpts and attribution.
- [x] Add source-verified runner reusing current critic and article writer; record separate labelled metrics and unlabelled generation observations.
- [x] Verify tampered evidence, wrong identities, malformed outputs, deadlines and no publication capabilities with focused tests.
- [x] Run actual local evaluation once, inspect every generated proposal, and preserve all outcomes.
- [x] Check collection/policy preservation, run backend checks and document results in lesson 50 and progress.

Files: `evals/movie-rag/real-film-facts/dataset-v1.json`, `backend/src/movie_companion/real_film_fact_eval.py`, `backend/scripts/evaluate_real_film_facts.py`, `backend/tests/test_real_film_fact_eval.py`, lesson/progress and evaluation README. Only the evaluator gains an optional limitations description; writer, critic, retrieval and publication policies stay frozen.

Outcome: baseline 18/18 matches, 6/6 useful approvals, 0/12 flawed approvals; seven actual generated facts/five automated eligible drafts. Inspection found citation and judgement gaps. All ten collections and writer/critic policy preserved. See lesson 50 for limitations and next corrective work.
