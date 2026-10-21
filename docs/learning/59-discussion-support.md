# 59. Complete evidence and a separate support reviewer

A quote can exist in the source and still be incomplete or irrelevant. This slice
adds two checks to the Wikipedia discussion path: recover complete sentences,
then ask a distinct local model whether the chosen sentences support the answer.
The script-assisted discussion path and saved facts/quiz banks keep their existing
policies.

## Follow the makeup question

Ask: **How did Ledger's facial expressions help create the Joker's makeup?**

The previous pipeline retrieved the right production passage but cited only a
continuation. It omitted the instruction to scrunch his face. The repair uses the
original source offsets to recover the complete sentence about the instruction,
application and resulting cracks/textures. That sentence crosses windows `073`
and `074`, so code assigns both original IDs to it.

The flow is:

```text
React question panel
  → POST /api/movies/155/questions
  → registered source + spoiler permission + bounded inference slot
  → cached article/chunks/embeddings
  → embed question with nomic-embed-text:v1.5
  → unchanged hybrid top-three retrieval
  → recover complete source sentences with original-window provenance
  → llama3.2:3b generates answer + selects offered sentences
  → Python validates exact selections and citation coverage
  → qwen3.5:9b reviews question + answer + selected sentences
  → supported: return answer; unsupported/uncertain: abstain
  → React displays answer and existing expandable source cards
```

This is explicit Python orchestration. No LangChain knowledge is required. Both
models run locally through Ollama, sequentially; this is not a parallel-agent
comparison. The second model has no shell, arbitrary URLs or publication tools.

## Why not re-embed everything?

An embedding helps *find* a useful window. Sentence recovery controls *what exact
text* reaches generation. We can improve the latter without changing the index.

`EvidenceStore.load_snapshot` now attaches an optional `PassageLocation` to each
loaded passage. It records the validated full source, source fingerprint, section
boundaries and the original window's start/end offsets. The full source string
is shared in memory. Stored passage IDs, text, vectors, Chroma metadata and the
snapshot fingerprint remain unchanged. Existing snapshots are reused.

For example, if a sentence spans positions 1,900–2,100 and a selected window ends
at 2,000, context recovery finds the eligible neighboring window covering the
remainder. It does not guess overlap from repeated words. Code checks that each
window equals its source slice and belongs to the same movie, revision, section
and embedding model. Spoiler-ineligible windows cannot complete a sentence.

`discussion_context.py` permits at most six generation windows, 36 offered
sentences, 600 characters per sentence and three contributing IDs per sentence.
The final answer still has at most three citations. Oversize or uncovered
sentences are skipped; they are not clipped into supposedly complete evidence.
Learning fixtures without locations can use their own complete sentences but
cannot gain guessed neighboring context.

The original top-three retrieval callback remains unchanged. Evaluations record
expanded generation IDs separately. Otherwise adding neighboring windows would
artificially improve a metric called hit-at-three.

## Who chooses the citations?

The generator chooses verbatim text from code-owned options. Python owns the
mapping from text to original window IDs and rechecks its coverage. A sentence
crossing two windows receives two citations. The model cannot invent a URL or
citation ID.

The HTTP response shape is unchanged. The UI shows the original bounded window
excerpts in its existing source cards. Two cards can therefore jointly support a
complete sentence; neither window is rewritten in storage. The full selected
sentence and all contributing IDs are available in development grounding traces.

A `grounding` trace records a proposed answer's selections **before** support
review. A rejected proposal can still have valid quote provenance in that trace.
Use the final response plus `support_review` verdict to determine whether the
answer reached the user.

## What does the reviewer check?

`discussion_support.py` sends the question, proposed answer and at most three
selected sentences to `qwen3.5:9b`. It receives strict JSON:

```json
{"verdict": "supported", "reason": "The evidence states the requested action and reason."}
```

The allowed verdicts are `supported`, `unsupported` and `uncertain`. Only the
first allows an answer through. Code validates the keys, values and bounded
reason independently of Ollama's response schema. Malformed output or service
failures follow the existing recoverable error path; there are no extra model
retries. Generator abstentions skip the reviewer.

The prompt asks about every factual claim, including who did what, causation,
negation, quantities and chronology. A why-question needs evidence of the stated
reason; two adjacent events do not establish causation. Both inputs and source
text remain untrusted data, including instructions embedded inside them.

This is a model judgment, not proof. The reviewer can accept an unsupported
answer or reject a useful one. Using a different model does not make their
errors independent. Exact quote validation establishes location; semantic review
provides additional evidence of support. Neither establishes universal truth or
prompt-injection resistance.

## Operational cost and scope

A supported Wikipedia answer now usually needs one query embedding and two chat
calls rather than one. The reviewer checks the installed model's pinned digest
via `/api/tags`, disables its thinking mode and caps output at 512 tokens. The
existing 180-second service deadline and inference slot cover both calls. Model
loading and swapping can add substantial latency on a local machine. Sequential
observations are not a multi-user throughput benchmark.

Install the already selected reviewer model with `ollama pull qwen3.5:9b` if it is
missing. The app does not automatically download models. Hardware requirements
and admission control need measurement before deployment.

Standalone learning helpers retain `verify_support=False` by default to preserve
their focused exercise contracts. The actual Wikipedia question pipeline
explicitly sets it to `True`. Existing script-assisted discussion and quiz/fact
verification remain separate, and are not newly qualified by this change.

## Read the code in this order

1. `backend/src/movie_companion/passage_location.py`: source offsets and identity.
2. `evidence_store.py`, `load_snapshot`: attach locations to saved passages.
3. `discussion_context.py`, `build_discussion_context`: complete sentences and coverage.
4. `grounding_learning.py`, `_parse_supported_answer`: validate selections and bind IDs.
5. `discussion_support.py`, `review_support`: one bounded local review.
6. `movie_qa_learning.py`, `answer_movie_question`: connect the stages.
7. `movie_questions.py`, `_answer`: attach trusted URLs/revisions for the UI.
8. `frontend/src/components/movie-question-panel.tsx`: render answer/source cards.

The measured results and retained failures appear below and in the
[comparison inspection](../../evals/movie-rag/coverage/discussion-support-review.json).
Reproduction commands are in the [coverage README](../../evals/movie-rag/coverage/README.md).

## Actual evaluation results

The final seventeen-case comparison passed **16/17** automated checks versus
**15/17** for the frozen Lesson 58 baseline. Both retrieved annotated support in
**14/14** answerable cases and correctly abstained on **3/3** missing-data cases.
Neither had a response-validation error. Candidate median duration was
**8.018 seconds**, baseline **2.729 seconds**, in alternating sequential local
runs. These are whole-pipeline observations, not isolated reviewer timings.

The complete makeup sentence now cites both contributing windows. Arrival's
future-visions case still fails: its generated future-premonitions answer is
rejected because the selected sentences identify Banks while the question uses
Louise. The selections also omit the most explicit premonitions sentence. We
retain this failure; the next fix should supply adequate identity/relation
context without allowing the reviewer to substitute remembered movie facts.

Twelve separate frozen support controls check identity, reason, time, negation,
numbers, missing context and one injected-verdict example. The current distinct
reviewer matches **11/12**, with **one false acceptance** and zero false
rejections on those controls. It wrongly approves a causal explanation even
though the evidence states a different reason. Earlier prompt/model variants
remain in `evals/grounding/support-review-*.json`. Repeated tuning makes these
development controls, not an independent safety benchmark.

Some passing answers still choose extra sentences. The makeup generator also
adds the given name John from another part of the generation window, although
its selected sentence only says Caglione Jr. This is another reason not to
equate an automated pass or reviewer approval with full claim entailment.

Verification: **1,002 backend checks** and **16 focused browser checks** pass.
All eleven saved banks and the existing script policy/Inception expansion gate
remain unchanged. No frontend source changed in this slice.

The first comparison was rerun because its context file changed on disk while
inference was running. Historical outputs are preserved; the final `sentences-v2`
reports use the frozen final source. This is why recording hashes requires a
stable evaluated artifact, not merely hashing whatever file exists afterward.

Next quality work: complete identity/relation context, a stronger causal-support
inspection and fresh independently labelled cases before wider automatic
preparation. Support checking improves the flow but does not qualify production
safety or automatic publication.
