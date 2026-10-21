# Learning 77: Replacing weak quiz questions safely

This stage tried to replace the 34 saved quiz questions that the earlier narrative audit marked as too granular. It did **not** update the live quiz banks.

## Why replacement is a separate workflow

Finding a weak question is easier than writing a safe replacement. A replacement must address the intended story idea, use an exact released-film citation, have one correct option, test narrative understanding, avoid existing topics, and preserve the bank's publication history.

A model saying that a draft “looks good” cannot establish those conditions. PlotSpot therefore treats writing, deterministic validation, semantic criticism, editorial review and publication as different steps.

## The pipeline used here

`quiz_replacement_workflow.py` first binds every review target to its exact saved question. It compares the movie ID, question ID, wording, selected answer and citation fingerprint with `data/movie-content.db`. If the bank has changed, the run stops before inference.

The local `qwen3.5:9b` writer receives the old question, a replacement brief, the exact released-film excerpt and the remaining questions in that movie's bank. It may return one draft or abstain. The model has no tools and no publication function.

Code then checks the returned target ID, four distinct options, exact evidence-quote membership, literal selected-answer support, granular-recall wording and near-duplicate wording. Survivors go to the existing structured critic, which independently labels citation support, option correctness, distractor plausibility, content category, narrative focus and significance.

A malformed multi-item critic response is retried once as isolated single-item reviews. Repeated invalid output fails closed. Finally, the assistant performs an editorial review of critic-accepted candidates.

## What happened

The writer returned 34 drafts. Only 15 passed the deterministic checks, and only 9 passed the structured critic. Editorial review retained one candidate for a later publication review:

> What conflict threatens Simba's future rule while he grows up under Mufasa's watchful eye?

The remaining eight critic-accepted drafts were rejected because they copied whole evidence sentences into answer choices, retained counts or durations that the brief asked to remove, asked vague action questions, or claimed a relationship not established by the excerpt.

This low conversion rate is useful evidence. The initial source excerpt often supported the old granular fact but not the broader narrative question requested by the replacement brief. Prompt changes alone cannot repair missing evidence. The next pass should retrieve broader plot passages from the pinned multi-source corpus before asking the writer to try again.

## What the checks prove

They prove that the workflow binds drafts to the current bank, rejects several measurable failure modes, recovers from one malformed critic batch, checkpoints progress and cannot publish.

They do not prove that the one retained candidate is ready for users. The labels are assistant and local-model judgments, not independent human evaluation. A complete replacement set still needs broader evidence, novelty review against the final combined bank, a fresh integrity audit and a new atomic publication receipt.

## Files to inspect

- `evals/movie-rag/quiz-narrative-quality/replacement-candidates-v1.json` contains writer, code and critic results.
- `replacement-candidates-v1.md` is the readable first-pass table.
- `replacement-editorial-review-v1.json` records the final assistant decisions.
- `replacement-editorial-review-v1.md` is the concise editorial report.

## Concepts to remember

- **Fail closed:** uncertain or malformed output is withheld.
- **Separation of duties:** writer, critic and publisher are different capabilities.
- **Evidence adequacy:** correct evidence for an old question may be insufficient for a better question.
- **Checkpointing:** successful batches survive a later batch failure.
- **Publication authority:** a good candidate is still only a proposal until a reviewed atomic write creates a new receipt.
