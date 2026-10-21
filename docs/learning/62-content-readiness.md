# 62. Does the citation support the fact, and is the question really new?

The research workflow now has an extra readiness layer. Its output is still an
internal inspection report. This layer can withhold candidates; it cannot
publish them or turn an earlier rejection into acceptance.

## The gap in the previous workflow

A model could read a paragraph about mood boards and artistic influences,
produce a fact combining both, and select a sentence mentioning only the
influence. The paragraph might support the claim while the visible citation
does not independently support everything the user is told.

Similarly, two question stems can use different words and still test the same
fact. Asking why the aliens help humans and asking what future need motivates
their assistance are the same quiz topic when both answers are future human help.
Question-string similarity misses some paraphrases.

## Follow the code

- [content_readiness.py](../../backend/src/movie_companion/content_readiness.py)
  combines additional checks with the previous necessary eligibility decision.
- [quiz_novelty.py](../../backend/src/movie_companion/quiz_novelty.py) performs
  bounded saved-question/candidate topic review and validates all returned IDs.
- [research_preparation.py](../../backend/src/movie_companion/research_preparation.py)
  applies the layer after existing RAG generation and critic checks.
- [evaluate_content_readiness.py](../../backend/scripts/evaluate_content_readiness.py)
  runs fictional controls and replays unchanged Lesson 61 drafts.

The existing public script-assisted quiz expansion and article publication
policies are separate. This slice strengthens the internal research inspector.

## Fact readiness, in easy words

Start with the previous code checks and critic decision. If those reject the
candidate, readiness cannot approve it.

For a candidate that passed those necessary checks:

1. Recheck evidence against its exact source, movie, revision and offsets.
2. Require the selected quote to be a complete source sentence within the
   existing 20–250 character citation budget.
3. Withhold the two generic headings explicitly discouraged by the existing
   generator prompt: Visual Inspiration and Set Atmosphere. This small rule is
   not a universal editorial-quality classifier.
4. Apply the existing multiword-name check to the **citation alone**. A full name
   in a neighbouring paragraph cannot silently supply identity to the citation.
5. Ask the existing evidence-first Qwen reviewer whether the title and entire
   factual body follow from that quotation alone.
6. For up to two detected English purposes beginning with to/in order to and
   a configured verb, ask a separate WHY question about the exact preceding
   action. The claimed purpose must be explicitly supported by the same quote.

These model calls receive neither the surrounding paragraph nor remembered
movie information. The same fact may be true but still be withheld because its
chosen citation is insufficient. A missing name check does not prove the claim
false; it identifies an attribution gap.

For example, a quote saying the crew built spacecraft models in a water tank
can support a paraphrase about small spacecraft models. It cannot by itself
support an added purpose such as saving money. The purpose might appear elsewhere,
but the candidate must carry appropriate support before becoming ready.

## Why not check word overlap?

The words small models and miniatures can mean the same thing. High word overlap
can also hide a changed number, lost qualifier or invented reason. The source
and quote checks verify provenance; a model evaluates the meaning. These are
different jobs. A semantic model verdict remains fallible.

## Quiz topic novelty

The saved comparison contains each question **and its correct answer**. This
helps specify the answerable fact, rather than comparing vague themes.

The reviewer sees all forty or fewer saved pairs and at most three candidates.
It compares each candidate to the bank and to earlier candidates in the same
batch. No vector similarity threshold declares a candidate unique.

- Same stem: deterministic duplicate fast path, even if the proposed answer
  changed. A conflicting answer does not make the same question a new topic.
- Same answerable fact with different wording: model topic review withholds it.
- Same character but different decisions: can be new.
- Same scene but who versus where: can be different facts.
- Same answer string for different objects: not sufficient to call it duplicate.
- Ambiguous topic: uncertain, therefore withheld.

Clarity is a separate review call for topics labelled new. A topic can be new
while its stem is awkward or its pronoun unclear. The wording reviewer checks
whether the answer type fits the question: how asks for a process, what for an
identity, while how old/how many ask for numbers. It labels clear or needs_edit.
Duplicate/uncertain topics skip this call and report not_reviewed; that does not
assert grammatical clarity. A narrow code rule first withholds stems ending in
How is/are/was/were … revealed to be? It is not a general grammar checker.
Neither review replaces the existing factual/option critic.

## Why return match IDs?

The code gives the bank temporary aliases B1…B40 and candidates Q1…Q3. A duplicate
decision must name a real bank or earlier-candidate alias. It cannot refer to
itself, a later candidate or an invented B99. A new decision must have no matches.
The response must contain exactly one review per requested candidate.

These checks make the decision inspectable. Valid IDs do not prove the matching
topics are equivalent; they establish which supplied item the model claims is
a duplicate. Reports preserve the reason and the separate clarity judgement.

## What happens when the model fails?

An unsupported or uncertain fact is withheld. A duplicate, uncertain or unclear
question is withheld. Missing, malformed or failed reviews do not default to
acceptance. The report records a bounded error type and keeps ready IDs empty.
Caller cancellation still propagates; there are no repair loops or unlimited
retries. Local model calls remain sequential inside the inspection.

The previous eligibility observation is retained as `base_eligible_for_review`.
The stricter result is `eligible_for_review`; the readiness record explains why
it changed. This prevents a regression report from erasing what the old critic
actually approved.

## What do the evaluations mean?

Fourteen fictional control cases were frozen before the first model outputs.
The revised run keeps those labels unchanged and adds three positive cases before
its execution: an explicitly stated purpose, a natural how/process question and
a natural how-many question. The final set has eight fact and nine quiz controls. Positive cases matter: a gate that rejects everything is
not useful. Operational errors are not counted as successful model judgements.

The replay uses the exact Lesson 61 proposals, sources and a digest-pinned saved
Arrival bank. It does not regenerate or improve the writer during the comparison.
This isolates the effect of readiness checks. The old modules and outputs remain
in the readiness baseline archive.

Labels are assistant-authored development controls. The real drafts are already
inspected, consumed regression examples. Neither set is an independent human
holdout or evidence that all malicious requests or unsupported claims are blocked.

## Reproduce

From `backend`, using the existing private source/article caches, saved-bank
manifest and reviewed local Qwen model:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_content_readiness.py --output ../evals/movie-rag/research/readiness-new-run.json
PYTHONPATH=src .venv/bin/python scripts/inspect_movie_research.py --movie-id 329865 --mode parallel --report ../evals/movie-rag/research/arrival-readiness-new-run.json
```

Use new report paths and leave evaluated files unchanged while inference runs.
The evaluator writes intermediate reports so unsuccessful controls remain
available. Model digests, code/source/bank fingerprints and exact decisions are
recorded. None of these commands publish movie content.

## What the first attempt taught us

The first real-model run matched 13/14 control expectations. It wrongly called
an awkward how/revealed-to-be stem clear. The frozen-draft replay blocked the
two repeated quiz topics and the mood-board fact's missing identity/generic title,
but still approved the voice fact's unstated to-support-the-narrative purpose.
`readiness-v1.json` and `readiness-policy-v1/` retain those outcomes and source.

The revised layer therefore checks the question/answer type explicitly and adds
an action-specific WHY review after a generally supported fact with a detected
purpose. This uses the existing strict causal-review instructions rather than
assuming the overall supported verdict covers every small clause.

Purpose routing is a narrow English verb pattern. It is not a general parser,
and it can miss other causal phrasing or reject an awkwardly constructed claim.
Full-claim model review still handles the remaining text. At most one general
support call and two purpose calls run per eligible fact; no purpose call is
made when the general review already withholds it. Citation identity matching
also retains its English/Latin multiword-name limitations.

The helper explicitly permits only the fixed loopback Ollama client with
redirects disabled. Model failures or a changed local model digest withhold
readiness. These boundaries do not establish universal factual or injection safety.

## Keep topic reasoning separate from editing

The second model run fixed the unsupported narrative-purpose replay but matched
14/17 controls: the combined novelty/wording prompt confused what-versus-why
wording with distinct topics and equated different objects sharing a color. Its
awkward-stem response also failed validation. The output was withheld, but a
validation error is not counted as a correct semantic judgement.

The final design gives topic comparison its own prompt: compare the subject,
property/action/reason and answer, not the question word alone. Only new topics
receive the separate wording review. Exact duplicates and the narrow incomplete
how/revealed-to-be stem require no model call. Up to two quiz chat calls occur
for a batch; the model is still local and serial. Uncertain or duplicate topics
never gain eligibility through the wording review.

Earlier reports remain archived, including their source code. The v2 controls
keep every original v1 label and add three positive cases. Those labels remain
unchanged during the final rerun. These are measured development iterations,
not a claim that prompt refinement produces universal correctness.

## Tests pass; model evaluations can still fail

The final deterministic suite passes **1,090 backend checks**, including forty
new readiness/novelty checks. These verify code contracts, ID validation,
withholding, cancellation, local-only clients and integration. They mock model
judgements; they do not establish semantic accuracy.

The final actual-Qwen control run matches **14/17** expectations. All eight fact
cases match; three of the nine quiz cases wrongly withhold a valid new question:

- The age question is novel, but the wording reviewer incorrectly treats Twelve
  as unsuitable for an age answer and considers the daughter's pronoun ambiguous.
- The topic reviewer incorrectly equates a spacecraft color with a captain's
  uniform color merely because both answers are Blue.
- The first within-batch future-help question is new, but the wording reviewer
  incorrectly treats its future need as unable to explain why the aliens help.

These are observed overblocking errors, not changed labels. Positive controls
for a separate event detail, a natural how/process stem and a how-many stem do
pass. No source check or model consensus becomes a proof of truth.

In the frozen real-draft replay, the two previously eligible quiz questions and
two previously eligible facts are all withheld. The first quiz is a saved topic;
the second is withheld by the incomplete-stem check before topic inference. The
mood-board fact lacks selected-citation identity and has a discouraged title.
The voice fact's general support review still approves it, but its additional
WHY review cannot derive the asserted narrative purpose from the selected quote.
That separate check therefore withholds it.

This targeted repair does not qualify automatic publication or general novelty
accuracy. The three valid-question failures remain pending independent review;
we do not weaken withholding or change labels merely to make the score perfect.
Historical 13/14 and 14/17 attempts remain available alongside the final report.

## Complete flow and preserved content

The final actual Arrival research → RAG → generation → critic → readiness flow
completes both branches in **107.401 seconds**. It produces the same two quiz and
four fact proposals as Lesson 61. The four previously eligible drafts are now
withheld; the two existing rejections remain rejected. This is a single local
integration observation with extra model calls, not a speed or throughput result.

All eleven saved fact/quiz banks, the independent script policy fingerprint and
Inception's additional-question gate remain unchanged. No frontend or public API
job wiring changed. No new movie content was published.

Read `evals/movie-rag/research/readiness-inspection-v3.json` for source inspection,
three retained false withholds, exact report hashes and preservation checks.
`arrival-readiness-v3.json` records the complete flow. Both reports match final
module files and contain unchanged-code flags. Token usage is not captured by
these adapters.

Next: fresh independently reviewed topic/wording cases and conservative generation
that targets unused supported details. Integrate into durable preparation only
with a dependable, explicitly reviewed publication policy.
