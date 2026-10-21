# Learning 80: Filtering answer shape before generation

The answer-span-first workflow guaranteed that every correct option was copied from approved evidence, but exact text could still be a poor quiz answer. Examples included relative clauses, long source sentences and phrases beginning with conjunctions. This stage added deterministic answer-shape filtering before the local writer sees any options.

## What code owns

`quiz_answer_span_shape.py` applies small, explainable rules:

- keep answers between two and twelve lexical tokens;
- reject leading coordinating connectors and relative pronouns;
- reject incomplete trailing words and unmatched punctuation;
- recognize only explicit brief instructions to omit a duration, count or name;
- block numeric and duration-bearing spans when the brief explicitly requires omission;
- reject identity-only spans when the brief asks for a narrative role instead of a name; and
- rank concise standalone phrases above longer alternatives.

The rules never rewrite a source span. The writer receives only retained span IDs and exact text. Application code copies the chosen source substring into the correct option, while the model writes the question and distractors.

## Frozen comparison

All three runs used the same sixteen targets with assistant-approved broader evidence and the same pinned `qwen3.5:9b` model.

| Strategy | Writer drafts | Deterministic passes | Critic accepts | Editorial accepts |
|---|---:|---:|---:|---:|
| Free-form answer | 15 | 3 | 2 | 1 |
| Locked answer span | 13 | 13 | 9 | 1 |
| Shaped, locked answer span | 14 | 12 | 9 | 2 |

The shaped pass met its preregistered success criterion by improving editorial acceptance beyond one candidate. It retained two clean questions: Forrest settling into single fatherhood and Andy maintaining hope during imprisonment.

The deterministic and critic counts did not improve. That is a useful result: removing obvious fragments does not solve whether a selected answer fully matches the requested story relationship. The shaped pass also caused one improved Forrest running question to be rejected by the existing isolated-action rule, which shows that answer quality and question significance remain separate gates.

## Why seven critic approvals still failed editorial review

- one answer included the repeated child name that its brief explicitly asked to avoid;
- one answer did not grammatically answer a why-question;
- one covered the parents' transformation but omitted Chihiro becoming trapped;
- one described Fight Club's ritual rather than the requested purpose;
- one remained an appositive rivalry fragment;
- one included an incidental exact planet count; and
- one asked for the Endurance's name instead of its narrative role.

These failures show three independent quality layers:

1. **Grounding:** Is the answer an exact approved source substring?
2. **Answer shape:** Does it read naturally as an option?
3. **Question intent:** Does the question-answer pair satisfy the requested narrative concept without duplicating the bank?

A local model critic helps with the third layer but is not an independent human evaluator. Assistant editorial review remains required before whole-bank comparison.

## Recovery and safety

The run recorded one `no_natural_exact_answer_span` target and continued. Checkpoints now require the current policy identity, so an older locked-span checkpoint cannot be resumed as a shaped-span run. Invalid distractors and target omissions stay local to one candidate.

Across the three passes, four distinct candidates are now provisional: the earlier Lion King and Fight Club replacements plus the Forrest fatherhood and Shawshank hope questions. They are not a complete replacement set and have not passed final whole-bank novelty review.

No saved quiz, publication receipt or runtime gate changed.
