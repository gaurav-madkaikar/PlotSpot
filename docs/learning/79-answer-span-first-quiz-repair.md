# Learning 79: Answer-span-first quiz repair

The broader-evidence writer usually understood the requested story topic, but it often paraphrased the correct answer. That caused the exact citation guard to reject otherwise promising drafts. This stage changed responsibility: code chooses and locks possible source substrings first; the model may only choose a span ID and write the question plus three distractors.

## The flow

1. Start with the sixteen replacement targets whose broader evidence passed local semantic review and assistant source inspection.
2. Enumerate bounded word and clause spans directly from the approved excerpts. Each span keeps its source-citation index.
3. Give the local writer span IDs rather than permission to write an answer.
4. Copy the selected span into option zero in application code. The model cannot edit it.
5. Reject duplicate or answer-matching distractors as a writer abstention.
6. Run the existing deterministic narrative checks and structured critic.
7. Perform a final editorial review before any combined-bank or publication work.

This is a useful agent design pattern: give probabilistic components the creative task, but keep factual identity and authorization in deterministic code.

## Measured comparison

Both passes used the same sixteen assistant-approved evidence targets and the pinned local `qwen3.5:9b` model.

| Stage | Free-form answer writer | Locked answer-span writer |
|---|---:|---:|
| Targets | 16 | 16 |
| Writer drafts | 15 | 13 |
| Deterministic passes | 3 | 13 |
| Structured critic accepts | 2 | 9 |
| Assistant editorial accepts | 1 | 1 |

Locking the answer raised deterministic compliance from 18.75% to 81.25%. It did not raise final editorial yield. Eight of the nine critic-approved drafts still had product-quality problems: awkward clause fragments, an overlong copied sentence, an exact duration the brief asked to omit, partial coverage of the requested event, or weak distractors. Only the Forrest Gump ending question about settling into single fatherhood was retained from this pass.

The difference between critic acceptance and editorial acceptance is important. Exact grounding prevents one class of hallucination; it does not guarantee concise, natural or interesting quiz writing.

## Failure isolation

The first live run found a target whose excerpts had no span matching the replacement brief. The workflow now records `no_exact_answer_span` and continues. A later batch returned duplicate distractors; that candidate now becomes `writer_abstained` without discarding valid sibling targets. These are examples of production-style recovery: local failures are durable, visible and bounded.

## Next repair direction

The next writer should receive answer-shape constraints as well as source locking. It should prefer short noun, infinitive or complete-clause answers; reject spans beginning with connectors or relative pronouns; obey “omit count/duration/name” instructions; and abstain when no natural standalone answer exists. Any resulting candidates still require whole-bank topic comparison and explicit publication authorization.

All reports from this stage are proposal-only. The saved quiz banks and their atomic publication receipts were not changed.
