# Quiz replacement completion design

## Goal

Complete a reviewable replacement proposal for the thirty-one saved quiz targets
that are still unresolved after the answer-shape benchmark. The resulting questions
must test story, character motivation, consequence, relationship, theme or ending at
a general-viewer level. They must remain grounded in reviewed movie-specific evidence,
avoid granular trivia and remain unpublished until the complete replacement set passes
all gates.

This stage produces evaluation artifacts and a final proposal only. It cannot mutate a
saved quiz bank, issue a publication receipt, qualify runtime content or change the UI.

## Current baseline

The assistant bank review marked thirty-four questions for replacement. Subsequent
experiments produced three candidates that passed full-bank novelty review: one each
for *The Lion King*, *Fight Club* and *The Shawshank Redemption*.

The remaining thirty-one targets divide into three distinct failure classes:

- thirteen targets have assistant-approved evidence, but generation failed to express
  the requested narrative intent or a natural answer;
- seventeen targets lack evidence that explicitly supports the requested motivation,
  consequence, relationship or other narrative claim; and
- one *Forrest Gump* target has a grounded candidate whose novelty decision is
  ambiguous against an existing ending question.

The existing saved banks remain the immutable comparison baseline throughout this
stage.

## Selected approach

Use a three-lane, fail-closed completion workflow.

1. **Intent-constrained regeneration** handles the thirteen evidence-supported targets.
   It converts each editorial brief into a small structured contract before answer-span
   extraction and generation.
2. **Targeted evidence recovery** handles the seventeen evidence-gap targets. It searches
   the already ingested movie sources first, then obtains additional movie-specific
   sources only when the local corpus cannot prove the requested relation. Generation
   starts only after assistant evidence review accepts a source passage.
3. **Independent novelty adjudication** handles the one ambiguous *Forrest Gump*
   candidate. The candidate is compared by intent with the retained bank; an uncertain
   decision remains withheld, and the workflow may instead propose a different supported
   narrative target.

This approach preserves the strengths of the current pipeline while addressing each
failure at the layer that caused it. A single prompt-only retry would repeat known
failures, while replacing every target through fresh web research would add unnecessary
cost and source risk.

## Scope

### Included

- freeze the identity and current bank version for all thirty-one unresolved targets;
- derive and validate structured intent contracts for the thirteen supported targets;
- retrieve and review stronger evidence for the seventeen evidence gaps;
- make one independent novelty decision for the ambiguous candidate;
- generate candidates in bounded batches with the pinned local Ollama model;
- run deterministic, critic, editorial and whole-bank checks;
- create a complete proposal report that includes every original replacement target;
- measure recovery by lane and record every abstention or rejection reason.

### Excluded

- publishing any replacement or changing a content receipt;
- changing runtime quiz generation or the movie-page UI;
- using cloud-hosted language models;
- weakening literal answer support, citation binding or novelty thresholds;
- replacing a requested narrative concept with unrelated trivia merely because it is
  easier to source;
- production deployment.

## Architecture

### Frozen target manifest

A manifest binds each unresolved target to:

- movie ID, title and saved bank version;
- question ID, original question and original answer;
- replacement brief and lane assignment;
- hashes of the originating assistant review, evidence review and bank content; and
- any accepted evidence or provisional candidate already associated with the target.

The runner refuses to resume when one of these identities changes. A target may move
between lanes only through an explicit reviewed artifact that records the reason.

### Narrative intent contract

The supported-target lane represents the editorial brief as a deterministic record:

- `focus`: the story subject or relationship being tested;
- `relation`: one of `motivation`, `consequence`, `relationship`, `role`, `choice`,
  `theme`, `ending` or `story_rule`;
- `required_concepts`: words or compact concepts that the question-answer pair must
  express;
- `forbidden_details`: counts, durations, names or incidental facts explicitly excluded
  by the brief;
- `expected_answer_shape`: `reason`, `outcome`, `role`, `relationship`, `action`,
  `state_change` or `idea`; and
- `difficulty`: fixed to an accessible general-viewer level for this completion pass.

Contracts are prepared in a versioned proposal file and reviewed before generation.
They do not infer hidden symbolism. A required concept must be supported by the accepted
evidence or the target moves to evidence recovery.

The local writer receives the contract, reviewed excerpts, allowed exact answer spans
and the remaining questions in the same movie bank. It selects an answer span and writes
the question plus distractors. Application code copies the correct answer from the
selected evidence span.

### Targeted evidence recovery

The evidence-gap lane operates in two bounded stages:

1. Search complete plot sentences in stored provider, web and script-derived story
   sources using the target contract and original review explanation. Maintain source
   and publisher diversity caps.
2. When stored sources remain insufficient, collect a small movie-specific source set
   using the existing guarded research ingestion path. Queries combine the exact movie
   title and release year with the missing narrative relation. Retrieved pages remain
   untrusted data and must pass the existing URL, size, redirect and source-policy
   controls before ingestion.

Scripts are eligible only for story-backed quiz evidence. Search articles or trivia
pages are not accepted merely for mentioning the film; the excerpt must explicitly
support the requested relationship. At most eight ranked passages are released for
assistant evidence review. A rejection leaves the target withheld or permits one revised
retrieval query; it never releases unsupported material to generation.

### Novelty adjudication

Novelty compares the candidate's tested intent against every retained question in the
same movie bank, excluding only the exact question being replaced. Lexical difference is
insufficient: two questions are duplicates when a viewer would demonstrate essentially
the same knowledge to answer both.

The *Forrest Gump* fatherhood candidate receives a fresh review with an explicit
comparison between relationship change and child-name recall. If the reviewer cannot
make a confident distinction, the candidate stays withheld. The pipeline may then seek
a different evidence-supported target from the same replacement brief; it cannot
override the uncertainty flag.

### Candidate generation and validation

Targets run in batches of at most three. Every candidate must pass these gates in order:

1. **Grounding:** the correct answer and evidence quote match assistant-approved evidence.
2. **Answer shape:** the exact source answer is concise and grammatically usable.
3. **Intent:** required concepts and expected answer type match the structured contract;
   forbidden details are absent.
4. **Narrative quality:** the question tests meaningful story understanding rather than
   isolated recall or technical detail.
5. **Distractors:** four options are distinct, plausible, concise and of the same type;
   only one is supported.
6. **Novelty:** the tested knowledge does not duplicate a retained question.
7. **Whole-bank review:** wording, difficulty and topic balance remain coherent when the
   candidate is viewed with the complete movie bank.

Deterministic gates run before model critics. The local critic is advisory evidence for
assistant editorial review and never becomes publication authority.

## Data flow

1. Load the thirty-four original replacement decisions and the three full-bank-ready
   candidates.
2. Build and hash the thirty-one-target manifest.
3. Route thirteen targets to intent-contract review, seventeen to evidence recovery and
   one to novelty adjudication.
4. Promote only reviewed evidence and reviewed contracts to generation.
5. Generate in checkpointed batches through local `qwen3.5:9b`.
6. Run deterministic checks and the existing structured narrative critic.
7. Perform assistant editorial review on critic-approved candidates.
8. Run full-bank novelty review for every editorial accept.
9. Assemble a completion report containing the three existing ready candidates plus all
   new decisions, with source and policy hashes.
10. Leave publication fields false and verify that saved banks and receipts are unchanged.

## Checkpoints and error handling

- Every checkpoint includes policy, model name and digest, target-manifest hash, input
  artifact hashes and completed target IDs.
- A changed model, policy, source excerpt, bank version or intent contract invalidates
  reuse for the affected target.
- Malformed model output receives one bounded retry for that target. Repeated failure is
  recorded without aborting sibling targets.
- No natural exact answer span records `no_natural_exact_answer_span`.
- Missing required concepts records `intent_contract_not_satisfied`.
- Evidence that does not state the requested relation records
  `insufficient_narrative_evidence`.
- Ambiguous novelty records `novelty_uncertain` and remains withheld.
- Network, parser or source-policy failures are recorded per source and cannot broaden
  network access or weaken ingestion checks.
- Interrupted runs resume by immutable target identity and never discard already saved
  target-level decisions.

## Evaluation and reporting

The completion report measures each lane separately:

- targets attempted, evidence-approved and generated;
- deterministic, critic, editorial and whole-bank accepts;
- abstentions grouped by reason;
- exact-answer and citation-binding pass rate;
- duplicate/novelty rejection rate;
- local model latency and retry count; and
- new external sources accepted and rejected.

It also presents an end-to-end funnel for all thirty-four original replacement targets.
The three already ready candidates are pinned by hash and are not regenerated unless
their source or bank identity changes.

## Verification

Focused tests cover:

- manifest construction and stale-input rejection;
- intent-contract schema and allowed relation/answer-shape values;
- required-concept and forbidden-detail checks;
- lane routing and explicit promotion rules;
- retrieval bounds, publisher caps and one-query retry limit;
- target-level isolation for malformed model responses and source failures;
- independent novelty adjudication and uncertain withholding;
- complete-report accounting across all thirty-four original targets; and
- inability of any completion command to write a quiz bank or publication receipt.

The full backend suite, syntax checks and whitespace checks must pass. The publication
audit must remain at twenty banks, twenty receipts, 113 facts, 215 quiz items, 214 scored
questions and 332 citations.

## Success criteria

- Every one of the thirty-four original replacement decisions appears exactly once in
  the final proposal as ready or withheld with a concrete reason.
- Every ready candidate passes all seven gates and is grounded in assistant-approved
  evidence.
- No question relies on granular trivia, unsupported inference or technical wording.
- Supported targets improve through explicit intent constraints rather than relaxed
  quality rules.
- Evidence-gap targets generate only after stronger evidence is accepted.
- Ambiguous novelty remains fail-closed.
- Saved content, receipts and runtime qualification remain byte-for-byte unchanged.
- The report is reproducible from pinned inputs, policy versions and the local Ollama
  model identity.

## Implementation sequence

1. Add the frozen manifest and narrative intent-contract representation.
2. Add deterministic intent validation around the existing shaped-span writer.
3. Add bounded evidence-recovery orchestration using the current guarded source path.
4. Add independent novelty adjudication and complete-report assembly.
5. Run the three lanes in small batches, perform editorial review and record the measured
   comparison.
6. Run the full verification and publication audit without publishing content.
