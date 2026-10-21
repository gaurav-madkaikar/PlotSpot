# 39. Let the model assess evidence; let code make the decision

A single accept/reject answer concealed which quality rule the model evaluated. Our optional structured verifier now separates those assessments and retains them in the evaluation trace. This uses Pydantic schemas and ordinary async HTTP calls, without LangChain.

## The input now spells out the chosen answer

For a question whose options are `["The porter", "The station clerk", ...]` and `correct_index=0`, the backend adds:

```json
{
  "indexed_options": [
    {"index": 0, "text": "The porter"},
    {"index": 1, "text": "The station clerk"}
  ],
  "selected_answer": {"index": 0, "text": "The porter"}
}
```

This example abbreviates the four-option list. Actual calls include all four original options. The mapping is built from validated application data; the model cannot change it. It addresses the earlier critic's mistake of describing option zero as a different answer.

## What the model returns

Each assessment has an item ID, support status, content category, supported option indices, distractor plausibility and a short reason. For example:

```json
{
  "item_id": "Q1",
  "support": "contradicted_or_exceeds",
  "content": "eligible",
  "supported_option_indices": [1],
  "plausible_options": true,
  "reason": "The source gives the photograph to the station clerk, not the porter."
}
```

There is deliberately no model-selected final `decision`. An invented decision field fails strict parsing. For facts, the choice indices must be empty and plausibility must be null. For quiz questions, indices must be unique integers from zero to three and plausibility must be a boolean. Missing/extra/duplicate item IDs fail the entire affected review call.

## How code decides

`decision_for` rejects unsuitable content, implausible choices or claims exceeding the evidence. Missing required context produces uncertain. An otherwise supported question is accepted only if its supported option list is exactly `[correct_index]`. Multiple true options or a different correct option are rejected. A supported fact must also be classified as eligible unusual production background.

This makes the policy explicit and testable. It does not make model assessments true: if the model incorrectly calls plot content eligible, code can still derive a wrong acceptance. Unit tests establish the decision logic; real labelled evaluations measure the model's criteria.

## Independent fact and quiz branches

The first structured candidate evaluated facts and questions together. Its criterion traces showed that the model called obvious plot content eligible and treated plausible alternatives as invalid because they were not mentioned in the source. It matched 12/18 development labels, with five false approvals among thirteen expected-reject/uncertain items—worse than the original critic's four.

The next candidate separates fact and quiz assessments into two domain calls, with small illustrative category examples and a clarification that distractors need not be true or appear in the source. Each input batch has at most two model calls. Calls run sequentially on one local GPU; hardware allowing independent inference would permit a later parallel comparison. Splitting calls has a resource cost, so latency must be reported alongside quality.

That separated v2 still used a shared category vocabulary and shared instructions. Its development run matched 12/18 labels, reduced false approvals to 2/13, but accepted only 1/5 useful items. Several valid quiz questions were incorrectly labelled `plot_in_facts`, which belongs only to facts. This is a contract problem as well as a model-quality problem.

V3 restricts each branch's generation schema and backend validation. Fact categories exclude quiz-only labels; question categories exclude fact-only labels. Fact option lists are constrained to zero items and plausibility to null, while questions require a boolean. The two branches also receive separate task instructions. A malformed cross-branch category now fails validation instead of becoming a misleading rejection or approval. It still takes a real eval to see whether remaining semantic assessments improve.

The optional evaluator selects this verifier using `--verifier structured`. The original critic remains a separate baseline. Deterministic passage/quote checks happen before either domain call; rejected drafts cannot be overridden by the model. No reviewer has tools or publication permission.

The draft preparation command also accepts `--verifier structured` and records its verifier module and full criterion trace. Its default remains the baseline until selection is justified. Eight preparation batches allow at most eight generator calls plus sixteen specialist review calls with this option, bounded by the existing overall deadline. This still produces separate reviewable drafts, never SQLite publications.

## Run a development evaluation

From `backend`:

```sh
.venv/bin/python scripts/evaluate_content_quality.py \
  --verifier structured \
  --dataset ../evals/movie-rag/content-quality-development.json \
  --output ../evals/movie-rag/my-structured-development-run.json
```

Reports retain the individual assessments. Empty or malformed model responses remain evaluation errors, never useful approvals. Use a separate filename to preserve prior observations.

## Why another reserved set

The twelve earlier reserved cases have already been inspected. This stage freezes twelve new items in `content-quality-held-out-v2.json` before observing the new candidate's development results. Policy selection uses development results only. Once the fresh reserved run is inspected, those cases also become consumed regression evidence; future tuning needs another unseen set.

## Actual results and adoption decision

| Policy / partition | Matches | Useful approvals | False approvals | Time |
|---|---:|---:|---:|---:|
| Baseline, development | 12/18 | 4/5 | 4/13 | 58.46 s |
| Structured v1, development | 12/18 | 4/5 | 5/13 | 115.65 s |
| Structured v2, development | 12/18 | 1/5 | 2/13 | 112.21 s |
| Structured v3, development | 13/18 | 4/5 | 4/13 | 143.63 s |
| Baseline, fresh reserved | 7/12 | 3/4 | 3/8 | 43.02 s |
| Structured v3, fresh reserved | 7/12 | 3/4 | 3/8 | 86.91 s |

V3 passed the relative development gate. On fresh reserved cases it demonstrated no improvement in these aggregate metrics and took about twice as long. We keep the structured verifier **optional**, with the original default retained. Better contracts and inspectable assessments are architectural improvements; these observations do not establish better general semantic quality.

The baseline fresh run was started while v2 was under review, but its scores were not inspected until final v3 was frozen. V3 changes used development traces only. Baseline and v3 each received one run on the same fresh sources; no changes were made against either reserved outcome. The fresh set is now consumed.

Remaining errors include unsupported causal claims, strengthening some to all, poor distractor approval and unnecessary refusal of a supported item containing source instructions. One assessment called impossible options plausible while admitting in its reason that they were impossible. Structured fields expose contradictions; they do not eliminate them.

`content-quality-structured-comparison.json` records development selection and the final reserved evaluation. `structured-verification-outcome.json` compares both fresh runs and records the default/adoption decision. Exact implementation archives are under `evals/movie-rag/policies/`. No model response, approval flag or comparison result publishes content.

Validation: 561 backend checks passed, including criterion conjunctions, index mapping, branch schema restrictions, illegal/missing assessments, local-client restrictions, trace preservation and optional preparation routing. No UI changes or live-server restart were required.

## Questions and answers

**Is this multiple agents?** It has two specialist review branches plus a deterministic coordinator. Their value must come from measured quality and cost, not from calling them agents. They currently run sequentially to suit local hardware.

**Why not let the critic fix the answer?** That would mix verification and repair, making it harder to tell whether the original draft was valid. Reject first; a future bounded repair step can produce a new draft that passes all checks again.

**What can code guarantee?** Correct index mapping, unique/bounded index values, exactly one assessment per item, deterministic rejection precedence and the acceptance rule. It cannot guarantee that an LLM correctly understood the source.

**Can this publish automatically?** No. Relative improvement on small authored cases is insufficient for automatic publication. Reviewed movie content remains the serving baseline while we build evidence for quality and preparation jobs.
