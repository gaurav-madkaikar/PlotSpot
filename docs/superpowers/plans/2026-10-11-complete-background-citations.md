# Complete Background Citations Implementation Plan

> **For agentic workers:** Execute inline with the executing-plans workflow under existing authorization. No delegation, commits or publication in this slice.

**Goal:** Keep background citations complete through retrieval, generation and publication checks.

**Architecture:** A shared exact-span helper replaces both background regexes. Check quote membership independently of model judgement, including full source boundaries at publication. Preserve baseline artifacts and compare consumed cases plus cached publisher RAG.

**Tech Stack:** Python 3.12, existing Pydantic/httpx/Ollama/Chroma, pytest.

## Global Constraints

- Preserve all ten collections and story qualification.
- Keep writer/critic prompts unchanged; use fixed local models and cached approved sources.
- No publication, earlier-report overwrite or unseen-accuracy claims.
- Include the helper in the background fingerprint.

### Task 1: Exact source spans

Files: `sentence_spans.py`, `test_sentence_spans.py` in backend source/tests.
Interface: `complete_sentence_spans(text: str) -> list[tuple[int, int]]` with exact original offsets.

- [x] Test the full sentence `Screenwriters Cindy Davis Hewitt and Donald H. Hewitt wrote dialogue to match existing lip movements.`, decimals, honorifics, references and unfinished fragments; establish failure.
- [x] Implement conservative paragraph punctuation scanning; verify exact substring equality and bounds.

### Task 2: Retrieval and quote guards

Files: `background_fact_workflow.py`, `real_film_fact_eval.py`, `test_background_fact_workflow.py`.
Interface: add `complete_support_quote(evidence, proposal) -> bool`; publication also validates source-wide sentence spans inside the claimed origin.

- [x] Add regressions for clipped initial quotes and forged origins starting at `Hewitt`.
- [x] Replace both regexes, enforce membership in inspection/publication/eval, record incomplete quote failures and fingerprint the helper.
- [x] Run affected tests and preserve baseline report hashes.

### Task 3: Actual local evaluation

- [x] Record ten-collection/story-policy hashes and archive the old workflow.
- [x] Run six-film development rerun to a new path and inspect every output; compare the observed citation defect.
- [x] Run cached Arrival RAG inspection without publication and inspect quotes/proposals/errors.
- [x] Run backend checks, verify preservation, document findings in lesson 51/progress and report next steps.

Additional verified correction: sentence boundaries recognize numeric and single-letter reference markers. The intermediate initial-only report and deterministic replay are preserved. A generation-only runner mode avoids repeating unchanged labelled critic inference; its absence of labelled scores is tested. Final backend suite: 804 passing checks.

Completed: all final generated quotes are full original sentences; seven/five generated/eligible, four/one cached Arrival candidates/eligible, zero errors, no publication. All ten collections and story policy unchanged. See lesson 51 for remaining semantic issues and report-version distinctions.
