# Useful story quiz implementation plan

**Goal:** Make Generate more produce new, supported story questions while preserving source, ambiguity, spoiler and publication safeguards.

**Architecture:** Improve the released-film unit selection and retrieve script context for the proposed question, then run the existing blind-option and cross-source reviewers. Allow at most three different evidence batches and one literal-answer repair per batch, with bounded time and at most two accepted questions. Keep local generation serial under the shared inference lock. This is the first slice of the approved next-steps roadmap; broader content, job orchestration and community work follow separately.

**Constraints:** Local Ollama only; scripts remain unverified versions; no draft workspace; no source fabrication or automatic approval; at most two new questions per request, 40 saved questions, existing 180-second request deadline, atomic publication preserving facts. No commits or delegation required for this shared checkout.

## Design decisions

- Broadening script excerpts alone can include unrelated events and consume context. Relaxing corroboration can approve events absent from the released film. Prefer question-specific retrieval and bounded recovery with the same acceptance rules.
- Split released-film plot groups into complete sentences with exact origins for quiz selection; keep preceding context for pronouns when it fits the existing 600-character bound. Rank unused units using embeddings as a coverage heuristic, never a truth signal.
- Retrieve script passages around the actual proposed question and answer before review. Preserve scene boundaries, exact snapshot offsets, version labels and the 1,200-character excerpt bound.
- Retry with different plot units when generation or review withholds everything. Invalid model output cannot trigger unbounded loops or publication.
- Evaluation must measure retrieval and generation as well as the verifier. Retain baseline failures; reports distinguish inspections from publication and consumed regression data from genuinely unseen evidence.

## Tasks

### 1. Record the real baseline and label scene retrieval expectations

Files: `backend/scripts/evaluate_story_quiz.py`, `evals/movie-rag/story-quality/`.

- [x] Add a nonpublishing, bounded evaluator loading reviewed source snapshots and saved quiz copies; capture candidate counts, decisions, accepted questions and elapsed time without full screenplay text.
- [x] Run the unchanged policy on Inception and Matrix; retain its result.
- [x] Freeze real-movie scene expectations and explicit conflicting/unsupported candidate labels before retrieval changes.

### 2. Improve evidence selection and bounded recovery

Files: `backend/src/movie_companion/story_rag.py`, `story_verification.py`, focused unit tests and any extracted evidence helper.

- [x] Test complete exact-span sentence selection, exclusion of previously attempted units, movie/revision scoping, targeted script retrieval, strict repair bounds, three-batch stopping, duplicate suppression and rejected-candidate nonpublication.
- [x] Implement sentence selection and candidate-specific scene reconstruction, keeping existing blind-option and semantic review requirements.
- [x] Add one literal-answer repair using explicit failed checks; revalidate and review every repaired candidate.
- [x] Run focused checks and inspect local-model outputs; preserve failures honestly.

### 3. Validate and connect the useful policy

Files: evaluation reports, `backend/scripts/evaluate_story_gate.py`, private gate, learning note and progress.

- [x] Run verifier regressions and real-movie labelled checks; close activation on false approvals, errors or below-threshold useful acceptance. Preserve the single useful-case mismatch.
- [x] Inspect generation on both films, manually assess accepted questions for support, ambiguity, duplication and story focus. One useful Inception result qualifies that movie; Matrix stays unqualified.
- [x] Run backend regression checks and appropriate browser journeys; restart the backend with the evaluated implementation.
- [x] Exercise Generate more through the actual API, verify persistence and unchanged facts, document measured outcomes and limitations.

## Delivery evidence

- Final gate: 27/28 development/regression labels matched, zero false approvals/errors; useful real-film acceptance 3/4. The conservative Yusuf-recruitment mismatch remains visible.
- Final nonpublishing inspection: Inception one accepted question, Matrix zero; both saved collections unchanged. Expansion qualified only for Inception.
- Live Inception API: HTTP 200 in 90.90 seconds; saved quiz grew from 10 to 11, original items preserved, IDs unique and all facts unchanged. Reloaded API and browser show the new fifty-years question; correct-answer feedback has no citation disclosure.
- 679 backend checks, seven relevant browser journeys and frontend production build passed. Backend restarted with the evaluated code.
- Broader generation coverage, faster background execution and an unseen real-film benchmark remain later work. These results do not establish general production accuracy.

## Later approved roadmap slices

1. Broader verified fact/quiz coverage with interviews/news background sources.
2. Persistent jobs and justified parallel source/tool orchestration with bounded recovery and tracing.
3. Community threads/replies and spoiler controls; accounts when user wiring is introduced.
4. Consolidated AI evaluation/CI and a reproducible portfolio demo. Existing CI already covers deterministic backend/frontend checks.
