# Narrative quiz quality: story understanding over trivia recall

## What changed

PlotSpot now treats factual correctness and narrative value as separate requirements. A question can have a supported answer and four valid options yet still be unsuitable when it only tests recall of a minor name, place, object, number, duration, quotation or technical term.

Both quiz writers now prioritize turning points, character choices and motivations, causes and consequences, meaningful relationship changes, story rules, objectively supported themes and resolutions. They explicitly avoid isolated granular recall. Screenplay material remains supplemental context; released-film evidence still owns the answer.

The semantic critics return two bounded labels:

- `narrative_focus`: turning point, choice or motivation, cause or consequence, relationship, theme or concept, ending or resolution, story rule, or granular recall.
- `narrative_significance`: central, supporting, or granular.

Code accepts only meaningful focuses with central or supporting significance. The model supplies the classification, while code owns the decision. Existing support, unique-answer, distractor, novelty, citation and corroboration gates still run.

## Why a prompt alone is insufficient

A writer prompt changes the probability of good output but does not enforce it. The separate critic can identify a granular candidate, and `narrative_eligible()` applies the same explicit rule every time. This gives the pipeline a traceable rejection reason and makes the behavior testable.

The finer focus categories are useful for auditing quiz variety, but they are not perfectly exclusive. A question can reasonably be both a turning point and a theme question. The production gate therefore relies on meaningful versus granular eligibility rather than demanding exact agreement on every focus label.

## Measured development result

The authored development set has 40 questions: 20 meaningful story/concept questions and 20 intentionally granular recall questions. With local `qwen3.5:9b`, bounded batches produced:

| Metric | Result |
|---|---:|
| Meaningful-question retention | 100% |
| Granular-question rejection | 100% |
| Eligibility accuracy | 100% |
| Exact focus agreement | 82.5% |
| Exact significance agreement | 92.5% |

These labels were authored during development and are not an independent held-out benchmark. The examples do not provide full story evidence, so the result measures question-type classification rather than answer correctness or citation support.

The read-only published-bank audit inspected 214 scored questions across 20 movies and flagged 55 for semantic review: 20 isolated-location, 13 isolated-object, 12 isolated-name, and 10 exact-count or duration prompts. Flags are deliberately conservative review requests. They neither prove a question is weak nor authorize automatic deletion, replacement or publication.

The policy fingerprint invalidated the previous script-assisted expansion gate, as intended. A fresh non-publishing inspection generated six narrative-oriented seeds across Inception and The Matrix but retained none because screenplay corroboration was insufficient. The legacy frozen gate then closed at 2/3 useful accepts because its third positive is an isolated-location question that the new policy intentionally rejects. Saved quizzes remain available, while script-assisted “Generate more” stays disabled until a narrative-aligned gate is preregistered and passes. The failed gate and clean inspection remain preserved rather than relabelled after observing their output.

## Narrative-aligned qualification result

A separate `cross-source-narrative-v1` family was frozen before its first model run. It contains eight development cases, eight reserved cases, four adversarial cases and eight pinned real-film cases. The synthetic positives test motivation, consequence, relationship change and story rules; negatives test granular recall, source conflict, wrong causality and multiple valid answers. File hashes, thresholds and partition order are recorded in `preregistration.json`.

Development and reserved both passed 8/8 with all useful questions retained and no false approvals. The adversarial partition passed three of four cases with no unsafe approval, but it retained only one of two useful questions. The reviewer correctly ignored the injected command as an instruction, yet incorrectly treated that text as a contradiction to the screenplay event. Useful acceptance was therefore 50%, below the frozen 75% threshold. The gate closed and the real-film partition remained unconsumed. This is a safe false negative and a useful diagnosis: sanitising instruction-like text and judging narrative agreement are related but distinct tasks.

The runner now accepts explicit dataset and real-case paths, so later policy versions can use a new frozen family without overwriting or silently reusing this consumed one. Script-assisted expansion remains disabled.

## Saved-bank semantic review

The 55 wording flags were reviewed against their saved answer, explanation and citations. The proposal keeps 21 questions where the apparently simple object, name or location is tied to a turning point, choice, story rule or resolution. It recommends replacing 34 questions that test isolated recall or duplicate a stronger item. Each replacement has a concrete narrative target, but no replacement text has been published: it still needs broader evidence retrieval, option review and the normal reviewed-publication step.

The proposal is an assistant semantic review rather than an independent human annotation. It deliberately leaves all saved collections unchanged.

## Blinded answer review

The separate 24-output assistant-blinded answer review scored the direct workflow at 7/12 and the specialist workflow at 8/12, an 8.4-point difference. Both safely handled all six private, missing-data and prompt-injection cases. Common answer failures included ambiguity, incomplete specificity, improper abstention, invalid output and missing units. This is an assistant review, not independent human validation, and the sample is too small to establish superiority.

## Reproduce locally

From `backend`, with Ollama running:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_quiz_narrative_quality.py \
  --output ../evals/movie-rag/quiz-narrative-quality/qwen3.5-9b-v1.json

PYTHONPATH=src .venv/bin/python scripts/audit_quiz_narrative_quality.py \
  --output ../evals/movie-rag/quiz-narrative-quality/published-bank-audit-v1.json \
  --markdown ../evals/movie-rag/quiz-narrative-quality/published-bank-audit-v1.md

PYTHONPATH=src .venv/bin/python scripts/evaluate_story_gate.py \
  --dataset-dir ../evals/movie-rag/cross-source-narrative-v1 \
  --real-cases ../evals/movie-rag/story-quality/real-movie-cases-narrative-v1.json \
  --report ../evals/movie-rag/story-quality/gate-narrative-v1.json
```

The evaluator uses ten-question batches and writes progress after every batch. The audit opens both SQLite databases read-only and cannot alter saved content.

## What remains

The 34 proposed replacements need evidence-grounded generation and reviewed publication. The screenplay reviewer needs to distinguish malicious non-story instructions from actual story contradictions, followed by a fresh unconsumed adversarial and real-film set. A held-out set should be labelled by independent reviewers before claiming general quality. Future evals should also measure quiz difficulty, thematic diversity, spoiler handling and player satisfaction.

## Instruction isolation and bounded recovery follow-up

The first follow-up failed safely because the critic treated a malicious screenplay instruction as a story contradiction. PlotSpot now builds a separate model-facing evidence view that removes only high-confidence instruction segments. Original source text remains unchanged for provenance, citation and literal-quote validation. Ordinary dialogue such as “ignore the bell” stays visible, while underlying story conflicts remain after an instruction segment is removed.

The next fresh gate exposed a different reliability failure: the local model duplicated a structured assessment ID. The reviewer now gets one bounded schema-repair attempt with a generic correction; it never receives or repeats the malformed output. A second invalid response still fails closed.

The final `cross-source-narrative-v3` run passed development 8/8, reserved 8/8 and adversarial 4/4. It retained every useful synthetic narrative question and rejected every granular, conflicting, ambiguous and secret-request case. The real-film partition matched 5/8: all four expected rejections were safely rejected, but only one of four useful questions was accepted. One Inception case lacked screenplay corroboration, one was classified as granular, and one exhausted the bounded response contract. With 25% useful real-film acceptance against the frozen 75% threshold, the gate remains closed. This result isolates the remaining problem to real-film screenplay selection and review reliability rather than the instruction boundary.

Because the real-film prerequisite did not pass, the 34 saved-bank replacements remain review proposals. Generating or publishing them now would bypass the qualification order recorded in the plan.

## Released-seed review and ranked fallback

The next iteration split quiz generation into clearer stages. The writer can propose up to three released-film seeds. A separate released-evidence critic rejects unsupported question/answer relations, multiple correct options and granular recall before the system spends time retrieving screenplay scenes. Approved seeds are ordered by narrative significance and focus, and the screenplay stage can try another approved seed from the same evidence window when the first lacks corroboration.

The non-publishing comparison improved real generation from zero retained questions for both Inception and The Matrix under v13 to one retained question for each under v15. Inception took 113.97 seconds and The Matrix 105.27 seconds in the final inspection. This is a two-film development observation, not a general quality or latency result. The two accepted questions were inspected, carried released-film citations and changed no saved content.

A fresh v5 gate then exposed two important limits. Synthetic and adversarial partitions passed 20/20, but the real-film partition retained only one of four useful questions, produced one structured option-proof error and falsely approved the granular identity question “Which crew member kills Cypher?”. The gate therefore closed and wrote no live authorization.

The follow-up v16 policy added two fail-closed protections learned from that consumed result: a narrow code-owned veto for isolated `who` and `which crew/team member` stems, and one bounded repair when the blind option checker paraphrases rather than copies its required literal support. A second invalid response still fails. At that stage these fixes had not yet passed a fresh real-film gate, so expansion remained disabled.

The next evaluation should broaden pinned screenplay coverage before freezing another holdout. Repeatedly drawing new labels from only Inception and The Matrix would provide increasingly weak evidence because the events and failure modes are already familiar.

## Expanded-source qualification and live gate

PlotSpot now has reviewed screenplay mappings for The Truman Show, Pulp Fiction, The Prestige and WALL-E in addition to the original three films. Each mapping pins an exact IMSDb path plus title, author and version markers. The parser accepts IMSDb's reviewed two-level legacy `<pre>` wrapper but rejects deeper nesting, oversized pages, changed headers and unrecognizable scene structure. The four new private snapshots contain 767 recognizable scenes and 1,392 indexed chunks in total. A screenplay remains an unverified draft and can never establish a released-film answer on its own.

The first expanded inspection exposed an evaluation-store failure in the shared Chroma index. The inspection runner now uses dedicated released-film and screenplay vector stores. This matters because an evaluation should neither depend on mutable app index state nor risk changing it. Chroma errors are recorded as failed cases instead of aborting the report.

Generation v17 changed one request to produce at most one verified question and bounded it to two evidence windows within the existing 180-second route deadline. A user can request another question later. The clean v17 development run completed in 80.02s, 72.41s and 56.53s, with no model or attempt errors. It accepted one WALL-E consequence question and one overly granular Prestige action question. V18 added a narrow deterministic veto for generic `What action does ... regarding ...?` recall. Its fresh development run completed in 61.29s, 43.21s and 38.92s, accepted the WALL-E cause-and-consequence question, rejected the Prestige action recall, and recorded zero errors. These timings are local observations, not deployment latency guarantees.

The `cross-source-narrative-v6` family was then frozen before reviewer execution. Its real-film holdout uses exact pinned spans from Pulp Fiction and The Prestige. Four positives cover motivation, consequence, rescue and the twins' central story method. Four negatives cover identity recall, generic action recall, wrong causality and missing screenplay corroboration.

The v18 gate passed:

| Partition | Matches | Useful accepted | False approvals | Errors |
|---|---:|---:|---:|---:|
| Development | 8/8 | 4/4 | 0 | 0 |
| Reserved | 8/8 | 4/4 | 0 | 0 |
| Adversarial | 4/4 | 2/2 | 0 | 0 |
| Fresh real films | 7/8 | 3/4 | 0 | 0 |

The single miss was a safe false negative on the Mia-overdose positive. The frozen threshold allowed one such miss but allowed no false approval or processing error. The live gate is now bound to the exact policy code fingerprint and local model digest. Story discussion can use the qualified cross-source policy for registered mappings. Quiz expansion is narrower: only WALL-E is authorized because it was the only v18 generation-inspection movie that produced a retained question. A verifier pass does not prove that every movie can generate a useful question.

No saved bank was changed during this work. The publication audit still verifies all 20 receipts and payloads: 113 facts, 215 quiz items and 332 citations. The 34 saved-bank replacement directions remain proposals and require evidence-grounded generation plus reviewed publication.
