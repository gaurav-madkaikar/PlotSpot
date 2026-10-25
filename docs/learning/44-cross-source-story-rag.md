# 44. Scripts connected to quiz and discussion

## What changed

For the three reviewed script mappings, the live backend can retrieve scene context and a released-film plot account together. The new path is controlled by a local evaluation gate bound to the implementation fingerprint and reviewed Qwen artifact. Missing/failed/stale gates retain the existing path. Movie facts and the draft workspace are unchanged; no user/admin wiring was added.

General story questions use this path. Production/metadata keywords continue through the full-article discussion path, which includes music/filming/cast sections. This routing is a simple heuristic and can misclassify mixed questions. Movies without a reviewed script retain their original behavior.

## Retrieval comes first

`MovieQuestionService.load_evidence` reuses the existing Wikipedia cache and validated embedding snapshots. `StoryRag.context` checks the source identity and full passage snapshot, filters Plot before ranking, then reconstructs two complete evidence units with exact original spans. These are W1/W2.

The script adapter reuses the private source and embedding caches. Discussion uses the user's focused question for script retrieval. Quiz preparation embeds the existing questions together with their correct answers and compares them with complete plot units. It prioritizes units least similar to previously tested material, then retrieves their script context. Coverage similarity guides selection, not factual acceptance. The small coverage comparison embeds units in bounded batches of 32; existing source/window vectors remain cached. The trace identifies coverage selection versus question relevance. The retrieval produces up to three non-overlapping embedding windows (S1/S2/S3), then reconstructs up to 1,200 characters of surrounding dialogue within the same scene. Released-film units stay bounded to 600 characters. The trace retains both the vector-window offsets and expanded scene-context offsets. Opening/title material is excluded from this live context to avoid title-driven hits masquerading as narrative evidence. A similar scene is only a candidate match, not proof of agreement.

## Generation is deliberately small

A request drafts at most two quiz questions or one discussion answer. The generator sees the evidence, source version warning, and existing quiz questions. It has no tools, arbitrary URL fetching, shell execution, publication tools or secret access.

The model returns source aliases, correct-answer text and three distractors. Python attaches the exact selected passages and inserts the answer at a deterministic location among the final four options. The answer must appear literally in released-film evidence, and the four options must be distinct. No model-written quote or index is accepted. For factual discussion answers, the answer must be a verbatim substring of the released-film passage; script-only additions are withheld.

The initial real Inception run exposed modified quotes and inconsistent indices; both were withheld. These are model contract failures, not reasons to relax support requirements. Moving transcription/index calculation into code addresses the mechanical errors while retaining semantic checks.

## Verification has two stages

For a quiz, a blind option check first receives the released-film evidence, question and four indexed options. It does not see the generator's chosen answer/index or the screenplay. It independently marks every option supported or unsupported and must provide literal evidence for each supported option. Code requires exactly the generator's selected index to be supported.

Then a separate cross-source review checks the entire question/answer relationship, agreement with the script, objective wording and plausible distractors. Wrong but plausible alternatives are expected. Zero/multiple supported answers, draft conflicts, missing evidence, subjective answers, malformed responses or uncertain assessments are withheld. The same local model runs the stages in separate calls; this reduces anchoring but does not make their errors statistically independent.

Discussion uses the cross-source review without scored options. A thematic reading must be explicitly marked as an interpretation. Python prefixes accepted readings with 'One possible reading' and the UI states that they are unscored. Definitive claims about director intent need actual support and cannot be invented from symbolism.

This is an LLM-assisted support gate, not a guarantee of truth or protection against every injection. Wikipedia is a secondary plot account, and retrieved windows can omit essential context. Additional sources, independent labels and broader evaluations remain necessary.

## Display and persistence

Discussion citations support the released-film account. A separate collapsible Script context shows the reviewed draft label/link, always with `released_film_verified=false`. The frontend permits only the three fixed script URLs. Script snippets are not silently presented as final-film citations.

Accepted new quiz questions are added through the existing explicit Generate more action. Publication is atomic, preserves production facts, merges citation revisions and checks the collection timestamp to prevent stale writes. Generated items are identified as generated. Failed generation/review leaves the saved collection unchanged. Serving an existing collection never calls a model.

Private traces record movie/source revisions, selected spans, decisions, model policy fingerprint and candidate hashes. They omit full screenplay excerpts and the user's question. Model decision reasons may describe story details; these files remain private. Stored original script snapshots stay unverified against the released film even when an individual event passes the cross-source check.

## Evals and their limits

The first cross-source reviewer matched 6/8 authored development labels and falsely approved a wrong cause plus an ambiguous multiple-answer question. The gate stayed closed. After adding blind option checks, it matched 8/8 development and 8/8 previously unused reserved labels, accepting all three useful cases per partition and none of the five negative cases.

Four additional adversarial cases tested useful evidence mixed with malicious instructions, a conflicting script carrying an approval instruction, and fabricated secret disclosure. All four matched their labels. No actions are possible through this model interface regardless of model wording.

These are small authored synthetic sets. Reserved cases use analogous relations with different characters/objects; they are not an independently collected real-movie benchmark. Once evaluated they are consumed. The subsequent generation-contract changes rerun these cases as regression checks, not new evidence of generalization. Real movie smoke results are recorded separately, including abstentions/errors rather than just successful outputs.

Run the complete gate from `movie-companion/backend`:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_story_gate.py \
  --report ../evals/movie-rag/cross-source/regression-report.json --enable
```

Thresholds are fixed: no false approvals, no errors and at least 75% useful acceptance in each development/reserved/adversarial partition. `--enable` closes the gate before the run and opens it only after every partition passes. Changing the fingerprinted implementation automatically closes the live path until evaluated and loaded again. The gate checks both the code fingerprint captured at module import and the current files, preventing a new on-disk evaluation from approving an older running process. Restart the backend after implementation edits. Repeated runs of consumed cases measure regressions, not unseen quality.

## Questions and answers

**Why not combine both sources into one paragraph?** Separate W/S labels preserve authority and expose contradictions. Mixing them would hide which version supplies a claim.

**Why is literal quoting insufficient?** A quote may contain the answer word while establishing a different relationship. The initial cause failure demonstrated exactly that. Semantic question/option support must be evaluated separately.

**Does the blind option check choose the answer?** It verifies whether all options answer the question from the evidence. Python compares that set with the answer position it constructed from the generator's answer text. Disagreement causes withholding, not automatic answer replacement.

**Why can a good script-supported question be rejected?** The available released-film passage may not corroborate that detail, retrieval may miss context, or the model may be overcautious. Track useful refusals as well as false approvals; do not weaken the evidence gate merely to fill a quota.

**Are facts generated from scripts now?** No. Scripts feed story context. Production facts keep their separate evidence purpose and pipeline.

## Final generation contract

Real generation subsequently exposed an answer-text/option mismatch and a factual response with an extra detail supported only by the script. The final contract asks the model for answer text plus exactly three distractors; Python inserts the answer into the final four options at a deterministic position. For factual discussion, the answer must be a verbatim substring of the selected released-film passage. This favors verifiable extracts over flexible paraphrasing. Interpretations retain cautious prose and separate review. No gate is opened merely because a model returned valid JSON.

To inspect generation without changing the saved quiz:

```sh
PYTHONPATH=src .venv/bin/python scripts/inspect_story_rag.py \
  --movie-id 27205 --question "Why does Cobb accept Saito's offer?" \
  --source-snapshot ../.cache/source-snapshots/27205.json --quiz \
  --report ../evals/movie-rag/cross-source/live-inception.json
```

Omit `--source-snapshot` to use the live Wikipedia adapter. The inspection command explicitly uses spoiler-enabled source content, has a 300-second deadline, and records validation failures as well as accepted items. `--quiz` generates for inspection only; the website's Generate more button performs the actual atomic save.

## Generation and verification are different evaluations

The verifier regression suite starts with supplied candidates. It measures whether the checks accept or withhold those candidates, not whether retrieval and generation will create good new questions. Real inspections exposed several candidates that failed: a paraphrased answer absent from the released-film passage, a question about a script-only action, ambiguous agreement and duplicate topics. Those failures were withheld rather than saved.

The current generation prompt chooses an exact answer span from the released-film source first, then asks a question fully answerable from that source. The script must corroborate the same relationship. No extra retry is introduced; abstention still leaves the saved collection unchanged. This prompt change must be assessed with real generation runs separately from the unchanged verifier regressions.

Current coverage is explicitly registered for Inception, The Matrix and Interstellar. Other movies continue through the existing source workflow. Automatically locating and validating arbitrary scripts, expanding independent real-movie labels, and improving useful generation coverage are subsequent work.

## Recorded result (11 October 2026)

Policy v8 passed all 20 consumed verifier regression labels: eight useful candidates accepted and twelve negative candidates withheld, with no model/validation errors. This is a regression result, not a broad safety estimate. The implementation passed 639 backend checks, 57 browser checks and the frontend production build.

The final reviewed-snapshot Inception inspection answered “Why does Cobb accept Saito's offer?” with: “In return, Saito promises to clear Cobb's criminal status, allowing him to return home to his children.” It included a Wikipedia citation and separate shooting-script provenance.

The same inspection proposed two new quiz questions and accepted zero. One passed released-film option verification but failed draft alignment; the other used answer text absent from the released-film passage. Earlier real trials also returned zero accepted new questions. No inspection changed the saved quiz. Real quiz-generation usefulness therefore remains unproven; verifier success alone must not be reported as an end-to-end success. The real trial report is `evals/movie-rag/cross-source/live-inception-v8.json`.

The next quality work should use independently labeled actual movie scenes, measure retrieval coverage in each source, and evaluate candidate yield, duplicates and valid refusals. A missing event in a retrieved draft window is insufficient support, not proof that the released movie contradicts the draft. Improve retrieval coverage rather than silently relaxing publication checks.
