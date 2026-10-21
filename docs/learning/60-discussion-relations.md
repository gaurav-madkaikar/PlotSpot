# 60. Giving the reviewer enough context and checking the requested relation

Lesson 59 found two failures: Arrival's question names **Louise** while selected
sentences say **Banks**, and the reviewer accepted a wrong reason just because
both events appeared in the evidence. These require different repairs.

## Missing context is different from incorrect reasoning

Consider these source sentences:

```text
Linguist Mira Cole joins the expedition.
Cole learns her visions show future events.
```

Question: “What does Mira learn about her visions?”

The second sentence provides the event, while the first connects the name in the
question to the surname used in the event sentence. The reviewer should receive
both. Without the first, using remembered film facts to assume the connection
would bypass our evidence requirement.

`discussion_context.py` now looks for one source sentence containing an adjacent
capitalized name pair. One token must appear in the question, a different token
in a retrieved anchor. It ignores common question/role words, scans only the
same validated source and section as the anchor, and accepts only one distinct
matching pair. Lowercase question words can match capitalized source names.
Missing/ambiguous matches add nothing; code never substitutes names in the user's
question or asserts a model-authored alias table.

This is a small English text heuristic, not a general entity resolver. Names
with unusual capitalization, initials, titles, multiple people or other scripts
may need richer context. Even a lexical match is not proof of identity: the
exact source sentence remains evidence for the model to assess.

The recovered option has `identity_context=True`. Its text and original window
IDs pass the same coverage checks as any support sentence. At most one such
option is included, within the existing six-window and 36-option budgets. It can
be a sentence already in the original anchors, because generation seeing a name
does not mean the reviewer saw it in the generator's chosen quotes.

## Follow the name context through the app

1. Original hybrid retrieval selects at most three anchors, unchanged.
2. Context recovery offers complete sentences and one optional name sentence.
3. The generator selects its supporting quotes as before.
4. Python adds the name sentence to review inputs and its IDs to final citations,
   even if the generator omitted it. Up to three selected sentences plus one
   context sentence may reach the reviewer.
5. If this exceeds the final three-citation limit, the answer abstains instead
   of silently dropping identity provenance. There is no extra model retry.
6. Only a supported final review returns the answer and citation union.

No database re-embedding or public response/UI contract change is required.
The same existing source cards show the original windows. Developer traces
separate original anchors, generation context, chosen quotes and mandatory
identity context.

## Why the evidence-first reviewer helps

Consider a fictional guard:

```text
The guard fixes a bell. She then leaves the tower to warn the villagers.
```

Question: “Why does the guard leave the tower?”

Proposed answer: “Because she fixed the bell.”

Word overlap is high and both statements are in the quote. That does not make
repairing the bell the reason for leaving. The evidence explicitly gives a
different purpose: warning villagers.

The Qwen reviewer now first derives an `evidence_answer` to the actual question,
then compares the proposed answer against it. Its output includes:

```json
{
  "evidence_answer": "She leaves the tower to warn the villagers.",
  "evidence_quotes": ["The guard fixes a bell. She then leaves the tower to warn the villagers."],
  "verdict": "unsupported",
  "reason": "Fixing the bell is an earlier event, not the stated reason for leaving."
}
```

The prompt distinguishes a requested reason from adjacent events and later
consequences. It accepts supported paraphrases and attributed interpretations.
All question, answer and source text are untrusted data. The model has no shell,
arbitrary fetch, collection-write or publication authority.

Python validates exact keys, text lengths, allowed verdicts and quote membership.
The reviewer cannot invent evidence or return supported without a quote. It also
cannot pair a supported verdict with the fixed “Insufficient evidence.” marker.

We do **not** compare answer similarity against a cosine threshold. Similarity
finds related text; it does not establish who did what or why. Likewise, a valid
quote and a structured `evidence_answer` do not prove the model compared correctly.
A reviewer can still extract a wrong answer, ignore a qualification or produce
an inconsistent judgment. Manual source review and broader evaluations remain
necessary.

## Calls, failures and scope

The live Wikipedia pipeline still makes one query embedding and up to two
sequential local chat calls: Llama generation, then Qwen support review. No new
LangChain framework or parallel agent is introduced. The review output cap
increases from 512 to 768 tokens to fit the structured extraction and quotes;
thinking remains disabled. Existing digest checks, timeout and inference slot
remain in place.

Generator abstentions skip review. Malformed review, timeout or unavailable
services follow existing recovery. Unsupported/uncertain reviews return a
citation-free abstention. Selected support traces precede the review; their
presence does not imply the answer reached the user.

Saved facts/quizzes and script-assisted discussion/quiz policies remain separate.
These changes neither publish new banks nor qualify automatic preparation.

## Tests and evaluation boundaries

Code tests check source/spoiler isolation, exact quote validation, missing or
ambiguous names, mandatory citation propagation, citation-budget refusal,
malformed structured verdicts, cancellation and the frozen old reviewer contract.
They are not measurements of model accuracy.

Twelve historical controls are copied unchanged into a twenty-case development
set. Eight additions cover name context, wrong people and adjacent-event/purpose
confusion. They were frozen before candidate output. All are assistant-authored;
they are not independent human labels or a safety holdout. The fixed reviewer
inspection is separate from the real seventeen-case movie pipeline comparison.

The baseline archive preserves Lesson 59's four modules. Both movie arms use
unchanged labels, original chunks/revisions, retrieval and model digests; calls
alternate sequentially. Evaluation records initial module hashes and detects
file changes during the run. We keep failed grades and prior outputs rather than
rewriting labels after an answer.

For source walkthrough, read `discussion_context.py`, the final stage of
`grounding_learning.answer_from_hits`, then `discussion_support.review_support`.
The orchestration remains in `movie_qa_learning.answer_movie_question`.

Measured results are recorded in the
[inspection report](../../evals/movie-rag/coverage/discussion-relations-review.json)
and the [coverage reproduction guide](../../evals/movie-rag/coverage/README.md).

## First fixed-control result

The current evidence-first reviewer matches **20/20** controls in
`support-relations-v5.json`, with zero observed false acceptances or false
rejections in that small set. Its first twelve expectations are unchanged from
Lesson 59, where the previous reviewer matched 11/12. The earlier wrong-reason
case now returns unsupported and derives the stated lure-the-criminal purpose.
Eight added controls test name context and different fictional causal examples.
This is an observed development improvement, not a production accuracy claim.
Some rejected cases still derive “Insufficient evidence” where an event is
stated: passing the binary verdict check does not grade every intermediate
`evidence_answer`. Manual inspection remains separate.

## What the first movie comparison revealed

The first candidate preserved the Dark Knight answers but still failed Arrival.
The name sentence was present; the reviewer correctly noticed that the chosen
evidence did not state the generated answer's unborn-daughter detail. The most
explicit premonitions sentence existed in the already offered pool but the
generator omitted it. This is an end-to-end context-selection failure, not a
reason to tell the reviewer to ignore missing support. The first `relations-v1`
reports retain that result and their unchanged labels.

`discussion_relation_context.supplemental_option` now recovers at most one
additional complete offered sentence. It requires two meaningful answer terms
absent from the selected evidence and explicitly present in that sentence.
Candidates are ranked by missing-term coverage, then answer overlap, then shorter
text and original order. This uses the existing English lexical tokenizer, not
an additional embedding or model call.

It never fetches new sources, searches other movies or rewrites text. Every
candidate was already eligible and offered for generation, and its source
coverage is revalidated. Original contributing IDs join the final citation
union. Up to five bounded sentences can reach review: three selections, one name
sentence and one missing-detail sentence. The final three-citation budget stays
in place; overflow abstains before review.

Lexical coverage is a context-selection heuristic, not support approval. A wrong
answer can share terms with true but irrelevant statements, so the evidence-first
reviewer must still check the requested relation and every claim. The heuristic
can miss paraphrases or add unnecessary context; it is deliberately bounded.
This supplement addresses the observed selection gap while retaining abstention
for unsupported answers.

## Inspect the reviewer, too

In the repaired Arrival run, the reviewer derives the explicit premonitions
answer from the supplemental sentence and returns supported. Its own
`evidence_quotes` nevertheless selects the original three sentences instead of
the most direct supplemental sentence. Exact membership validation passes, but
that selected subset is not a self-contained explanation of the verdict.

The final citations keep provenance for **all review inputs**, including the
name and supplemental sentences, rather than trusting the reviewer's quote
selection to remove sources. The answer's direct support therefore remains
visible in its cited window. This observed limitation is retained in the report;
we do not call the structured reviewer a formal proof or claim every intermediate
field is correct merely because the final binary grade passes.

## Final measured results

The frozen-code final comparison passes **17/17** movie checks versus **16/17**
for the Lesson 59 baseline. Both retrieve annotated support in **14/14**
answerable cases and abstain in **3/3** missing-data cases. No response-validation
errors occurred. Final twenty-control reviewer inspection matches **20/20**,
with zero observed false acceptances/rejections in this small set.

Candidate whole-pipeline median: **13.494s**; baseline **8.336s**. Both use
sequential local calls and the same model digests. Structured extraction and
extra context increase work. These timings include model loading/swapping and
are not a production throughput comparison.

**1,020 backend checks** pass. The first seven-worker browser run, concurrent
with inference, had three timing failures and thirteen passes. Rerunning without
inference using one worker passed **all sixteen** checks. No UI code changed;
we cannot isolate worker count from competing load in that comparison. Final
model v2 runs did not overlap browser test workers. Temporary configuration was
removed.

Next work should use fresh independently reviewed labels and compare bounded
parallel story/background research with a sequential baseline. Broad source
coverage, production admission/resource measurements, accounts/community and
preferences remain separate pending milestones.

## Live verification and preserved content

After restarting the owned backend, actual HTTP requests answered Arrival's
future-visions question, Dent's stated decoy reason and Ledger's makeup question.
Without spoiler consent, the same Arrival request returned
`spoiler_permission_required` with no citations. These single-request durations
were 14.462s, 12.178s, 12.763s and 0.006s respectively; they are smoke observations.

The existing live UI also answered a shorter Arrival wording and showed two
revision-backed source cards: the explicit premonitions sentence and the Louise
Banks identity context. Both were expanded and inspected. Screenshot:
`.cache/proof/discussion-relations.png`. The temporary test tab was closed;
its initial spoiler preference On remained On, and the user's tab was not
navigated. No new frontend behavior was introduced in this slice.

Post-UI checks confirm all eleven saved fact/quiz banks, the separate script
policy fingerprint and Inception's additional-question gate remain unchanged.
HTTP/UI observations and preservation checks are recorded in
`evals/movie-rag/coverage/discussion-relations-live.json`.
