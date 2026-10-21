# Quiz replacement completion: recovery without lowering the gate

This stage closes the accounting gap left by the earlier saved-quiz review. It does **not** publish replacements. Its purpose is to show how a production AI workflow handles incomplete evidence, plausible-but-wrong generations, retries and final abstention without losing track of any target.

## What problem did we solve?

The saved-bank review proposed replacing 34 granular quiz questions. Three candidates had already passed editorial and whole-bank novelty review. The other 31 could not all be treated the same way, so the workflow froze three lanes:

| Lane | Targets | Why it exists |
|---|---:|---|
| Intent | 13 | Evidence existed, but generation still needed an explicit story relationship and answer shape. |
| Evidence | 17 | Existing excerpts did not fully support the requested story question. |
| Novelty | 1 | A candidate existed, but its topic might overlap another saved question. |

The manifest pins the original review, saved-bank hashes and target identities. This means a changed question, bank or source review cannot silently enter a resumed run.

## The pipeline

1. **Freeze intent.** Each generative target has reviewed required concepts, forbidden details and an expected answer shape such as motivation, outcome, relationship or role.
2. **Recover evidence.** The evidence lane uses a contract-aware local BM25 query over validated provider, web and screenplay snapshots. A revised query is allowed once. Search snippets are never evidence.
3. **Lock the answer.** Code enumerates exact contiguous source spans. The model may select one span and write a question and distractors, but it cannot rewrite the correct answer.
4. **Repair once.** If a draft fails the intent contract, the rejected draft and exact deterministic problems are retained. One feedback-driven repair is allowed. Repeated failure is an abstention.
5. **Review independently.** Deterministic checks run before the narrative critic. Assistant editorial review then checks natural wording, answer type, evidence, intent and the remaining movie bank.
6. **Check whole-bank novelty.** Editorial accepts are compared with every other saved question for the movie. Only `new + clear` can become ready; duplicate, uncertain, unclear or malformed output stays withheld.
7. **Assemble exact scope.** The final report must account for all 34 original replacement decisions exactly once and revalidates bank, candidate, grounding, intent, editorial and novelty hashes.

## Measured funnel

Evidence recovery found assistant-acceptable packets for 12 of 17 targets. Five were rejected because the passages mentioned related events without explicitly proving the requested causal link:

- Forrest reconnects with Jenny, but the passages do not establish how that reunion redirects his journey.
- Lau and the anti-mob alliance appear separately, but the evidence does not explain how his capture advances the case.
- Sarah, Jess and Borden's later custody consequences appear, but the evidence does not connect both to Borden's double life.
- WALL·E and EVE reconcile, but the evidence does not link that change to their joint protection of the plant.
- Arrival shows worldwide craft and later cooperation, but not that the arrivals force countries to share interpretations.

The revised recovery query was attempted for all five and changed zero evidence packets, so the workflow stopped instead of broadening the claim.

Across the 30 generative targets:

| Stage | Retained |
|---|---:|
| Assistant-approved evidence available | 25/30 |
| Writer draft passed intent and deterministic checks | 11/30 |
| Local narrative critic accepted | 4/30 |
| Assistant editorial accepted | 1/30 |
| New and clear in final whole-bank review | 0/30 |

Seventeen targets used the one permitted intent-repair attempt. The repair raised deterministic passes from the first run's 7 to 11, but it did not justify lowering downstream quality gates. Editorial review rejected three critic accepts: a bare noun phrase with inconsistent option types, an incomplete exact answer span, and a stem that asked for a role while its answer only described a route. The sole editorial accept was withheld after its novelty review produced malformed output. The earlier ambiguous Forrest fatherhood candidate was also withheld as a duplicate by the independent reviewer.

The final proposal contains **3 ready and 31 withheld** decisions:

| Withheld reason | Count |
|---|---:|
| Intent contract not satisfied | 14 |
| Narrative critic rejected | 7 |
| Insufficient narrative evidence | 5 |
| Assistant editorial rejected | 3 |
| Whole-bank duplicate | 1 |
| Whole-bank review error | 1 |

The three ready rows are the previously reviewed Shawshank Redemption, Fight Club and Lion King candidates. This completion pass added no newly ready candidate.

## What the checks teach

A model can write fluent JSON and still miss the task. For example, a question about Mal after waking omitted the required connection to Limbo, and a question about Mann's booby trap omitted how the deception damages the wider mission. Literal concept checks caught those gaps before the critic saw them.

Literal matching can also be too rigid. The first run treated `rival` versus `rivalry`, `stolen oil painting` versus `stolen painting`, and `human habitation` versus `habitable` as different. The validator now permits only bounded inflection normalization and ordered alias tokens. The critic still rejected the newly admitted object/purpose recall questions, showing why a deterministic gate and a semantic gate solve different problems.

The local critic is useful for filtering unsupported or granular questions at scale, but it is not an editorial authority. It accepted awkward answer forms and later made a questionable duplicate argument about fatherhood versus recalling a child's name. The workflow records those decisions and fails closed rather than treating the model as ground truth.

## Reproduce the checks

From `backend/`:

```bash
.venv/bin/python -m pytest \
  tests/test_quiz_replacement_completion.py \
  tests/test_quiz_replacement_span_writer.py \
  tests/test_quiz_replacement_evidence.py \
  tests/test_prepare_quiz_replacement_completion.py \
  tests/test_provisional_quiz_replacements.py \
  tests/test_assemble_quiz_replacement_completion.py -q
```

The final artifact is `evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json`. It is proposal-only and contains no publication authority. The read-only publication audit still verifies 20 banks, 20 receipts, 113 facts, 215 quiz items, 214 scored questions and 332 citations.

## Limits and next decision

These are consumed development targets reviewed by an assistant and local model, not an independent human benchmark. Web discovery availability was limited during the revised recovery pass, and exact-span answers trade recall for strong grounding. A future attempt should begin with independently reviewed evidence or screenplay coverage for the five missing causal links and a fresh holdout. It should not tune prompts against these same 34 targets and claim a new evaluation result.
