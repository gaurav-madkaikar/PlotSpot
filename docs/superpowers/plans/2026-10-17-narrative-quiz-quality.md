# Narrative Quiz Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated quizzes test understanding of a film's story and central concepts while withholding technical or granular recall questions.

**Architecture:** Keep the existing evidence-first writer and code-owned acceptance pipeline. Add narrative focus and significance to semantic critic assessments, reject granular candidates in code, strengthen both quiz writers, and add an offline labelled evaluation plus a non-destructive audit for published questions.

**Tech Stack:** Python 3.12, Pydantic, pytest, local Ollama structured output, SQLite content banks.

## Global Constraints

- Correct answers and complete premises must remain grounded in released-film evidence.
- Screenplays remain supplemental corroboration and never become sole answer authority.
- Theme questions must remain objectively decidable from the supplied evidence.
- Existing safety, citation, novelty, and publication checks must continue to run.
- Existing published content is audited and flagged; it is not silently deleted or replaced.

---

### Task 1: Strengthen quiz generation instructions

**Files:**
- Modify: `backend/src/movie_companion/research_generation.py`
- Modify: `backend/src/movie_companion/story_verification.py`
- Test: `backend/tests/test_research_generation.py`
- Test: `backend/tests/test_story_rag.py`

**Interfaces:**
- Consumes: existing bounded released-film evidence and saved-question context.
- Produces: quiz candidates focused on turning points, choices, motivations, consequences, relationships, themes, story rules, and resolutions.

- [x] Add prompt-contract tests that reject the previous location/object/number preference.
- [x] Update both writer prompts with the approved narrative policy and spoiler-aware ending guidance.
- [x] Run focused writer tests.

### Task 2: Add code-owned narrative critic gating

**Files:**
- Modify: `backend/src/movie_companion/structured_content_review.py`
- Modify: `backend/src/movie_companion/story_verification.py`
- Test: `backend/tests/test_structured_content_review.py`
- Test: `backend/tests/test_story_rag.py`

**Interfaces:**
- Produces: `narrative_focus` and `narrative_significance` labels in critic assessments.
- Guarantees: `granular_recall` or `granular` assessments cannot be accepted by code.

- [x] Write failing decision tests for granular candidates and malformed metadata.
- [x] Extend the structured critic schemas and question-only prompts.
- [x] Gate acceptance in both research and script-assisted story workflows.
- [x] Run focused critic and story tests.

### Task 3: Add a labelled narrative-quality evaluation

**Files:**
- Create: `backend/src/movie_companion/quiz_narrative_quality.py`
- Create: `backend/scripts/evaluate_quiz_narrative_quality.py`
- Create: `backend/tests/test_quiz_narrative_quality.py`
- Create: `evals/movie-rag/quiz-narrative-quality/cases-v1.json`

**Interfaces:**
- Consumes: labelled meaningful and granular question examples.
- Produces: useful-retention, granular-rejection, classification accuracy, and focus-coverage metrics.

- [x] Define strict labels and report validation.
- [x] Add at least 40 balanced, movie-story examples.
- [x] Implement deterministic report calculation over supplied predictions.
- [x] Test malformed data, metric calculations, and zero-denominator handling.

### Task 4: Audit the existing published bank without mutation

**Files:**
- Create: `backend/src/movie_companion/quiz_narrative_audit.py`
- Create: `backend/scripts/audit_quiz_narrative_quality.py`
- Create: `backend/tests/test_quiz_narrative_audit.py`
- Create: `evals/movie-rag/quiz-narrative-quality/published-bank-audit-v1.json`
- Create: `evals/movie-rag/quiz-narrative-quality/published-bank-audit-v1.md`

**Interfaces:**
- Consumes: the saved SQLite movie-content bank.
- Produces: non-destructive review flags for questions likely to rely on granular recall.

- [x] Add conservative surface flags for names, exact counts/durations, isolated places, and minor objects.
- [x] Make the audit explicitly advisory so it cannot authorize deletion or publication.
- [x] Run the audit against the current 20-movie bank and preserve the report.

### Task 5: Verify and document

**Files:**
- Modify: `evals/README.md`
- Modify: `docs/learning/PROGRESS.md`
- Create: `docs/learning/76-narrative-quiz-quality.md`

- [x] Run all focused tests for writers, critics, evals, audits, and checkpoint replay.
- [x] Run the complete backend test suite.
- [x] Record measured results, limitations, and the distinction between assistant review and independent human validation.
