# Quiz answer-shape filtering design

## Goal

Improve the editorial quality of exact-source quiz answers without weakening factual grounding. The correct option must remain a contiguous substring of assistant-approved evidence, while awkward fragments, forbidden details and unnecessarily long answers are removed before the local writer sees them.

This stage remains proposal-only. It cannot update a saved quiz bank, publication receipt or runtime qualification.

## Scope

The change applies only to the answer-span-first saved-quiz replacement workflow. It will rerun the same sixteen evidence-approved targets used by the existing locked-span benchmark so the before-and-after measurements remain comparable.

It will not fetch new sources, change evidence-review decisions, alter the narrative critic, publish replacements or modify user-facing quiz behavior.

## Selected approach

Use deterministic answer-shape filtering and ranking before local-model selection.

This is preferred over a second model judge because it is reproducible, inexpensive and directly testable. It is preferred over introducing a full natural-language parser because the current failures are narrow enough to handle with bounded lexical and punctuation rules.

## Components

### Brief constraints

Parse explicit negative requirements from each replacement brief:

- `omit the exact duration`, `omit the year count` or equivalent blocks numeric and duration-bearing spans;
- `omit the count` blocks numeric quantity spans;
- `rather than its name` or `not the ... name` penalizes identity-only spans;
- equivalent explicit instructions are represented as small, versioned lexical patterns rather than inferred by a model.

The parser stays conservative. If a brief contains no recognized instruction, it applies no inferred exclusion.

### Shape validation

An answer span must:

- remain an exact, contiguous substring of one approved citation;
- contain between two and twelve lexical tokens by default;
- not begin or end with a coordinating connector, relative pronoun or incomplete preposition;
- not be a full copied sentence when a shorter supported phrase exists;
- contain meaningful content rather than only a name, number, place or generic word;
- avoid unmatched punctuation and obvious clause fragments.

Complete short clauses and concise noun or infinitive phrases are allowed. The filtering code returns explicit rejection reasons for tests and reports.

### Ranking

Retained spans are ranked using:

1. overlap with the replacement brief;
2. compliance with explicit brief constraints;
3. preference for concise standalone answer shapes;
4. source order and exact text as stable tie-breakers.

At most thirty candidates are released to the writer. If no candidate survives, the target records `no_natural_exact_answer_span` and stops locally.

### Writer contract

The writer receives span IDs and exact span text. It may choose one span ID and write one natural question plus three concise distractors of the same answer type. Application code copies the correct option from the chosen source span and never accepts model-written answer text.

Duplicate distractors, answer-matching distractors, invalid target IDs and cross-target span selections remain fail-closed. Candidate-level wording failures become abstentions and do not discard valid sibling targets.

## Data flow

1. Load the sixteen previously approved target/evidence bindings.
2. Extract exact substrings from each approved excerpt.
3. Apply brief-constraint and answer-shape rules.
4. Rank and cap the retained spans.
5. Ask pinned local `qwen3.5:9b` to select a span and write the remaining question fields.
6. Copy the answer in code and run existing deterministic checks.
7. Run the existing structured narrative critic.
8. Perform assistant editorial review and save a proposal-only comparison report.

## Error handling

- No qualifying span: record a target-level abstention.
- Malformed writer output: use the existing bounded structured-output behavior; repeated failure remains withheld.
- Invalid distractors: record a writer abstention for that target.
- Critic rejection: retain the decision and reason in the report.
- Interrupted evaluation: preserve the durable checkpoint and resume by question identity.
- Changed source, target or model identity: reject the run rather than reuse stale output.

## Verification

Unit tests will cover:

- exact-substring preservation;
- accepted noun, infinitive and complete-clause shapes;
- rejected leading/trailing connectors and relative fragments;
- duration/count exclusions derived from explicit briefs;
- stable ranking and bounds;
- no-span abstention;
- invalid distractor isolation;
- inability of model output to rewrite the correct answer.

The evaluation will compare the existing free-form and locked-span reports with the new shaped-span pass on the same sixteen targets. It will report writer drafts, deterministic passes, critic accepts and assistant editorial accepts. Editorial acceptance is the success metric; critic acceptance alone is insufficient.

Afterward, the complete backend suite, syntax checks, whitespace checks and twenty-bank publication audit must pass. The audit totals must remain 20 banks, 20 receipts, 113 facts, 215 quiz items, 214 scored questions and 332 citations.

## Success criteria

- No accepted answer violates exact citation binding.
- No target failure aborts unrelated targets.
- Editorial acceptance exceeds the current locked-span result of one out of sixteen without increasing publication authority.
- The report explains every withheld candidate.
- All automated checks and the publication audit pass.
