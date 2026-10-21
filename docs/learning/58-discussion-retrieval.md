# 58. Finding the right evidence and binding the citation

The Dark Knight inspection exposed two separate problems: retrieval could miss
a concrete story event, and generation could answer correctly while citing the
wrong passage. Fixing the first does not automatically fix the second.

## Follow one question through the app

Ask: **Why does Harvey Dent claim he is Batman?**

1. The existing movie question panel posts the question and spoiler consent to
   `/api/movies/155/questions`.
2. `MovieQuestionService` checks the registered movie, consent and its local
   inference slot. It loads the article's revision and saved Chroma embeddings.
3. `answer_movie_question` embeds the question with local Ollama.
4. `discussion_retrieval.py` searches only eligible passages from this movie.
   This explicit event question uses the Plot section of a classified article.
5. Vector similarity and exact-word ranking contribute candidates. The question
   receives at most three passages, including Plot passage ending in `012`:
   “Dent claims he is Batman to lure the Joker out …”.
6. `grounding_learning.py` offers verbatim support excerpts in both the prompt
   and the structured response schema. The local chat model answers and selects
   excerpts. Code validates those selections and maps them to source IDs.
7. The service adds the trusted source URL, revision and excerpt. React renders
   the answer and existing expandable source cards. No frontend contract changed.

The previous vector-only run missed that plot passage and abstained. The new
retrieval finds it, and the observed answer is **“to lure the Joker out.”**
This example demonstrates one repaired case, not universal correctness.

## Why combine words and vectors?

Embeddings help match related wording. They can also rank general commentary
above a small concrete action. Word search helps when names and actions are
stated explicitly.

**BM25** gives more weight to informative matching words, considering their
frequency and passage length. A name appearing throughout an article is less
informative than a specific action. This implementation keeps frequency
statistics over the eligible movie article even when searching just its plot.

**Reciprocal rank fusion (RRF)** combines positions rather than directly adding
incompatible cosine and BM25 scores:

```text
combined rank score = 1 / (60 + vector rank) + 1 / (60 + word rank)
```

The second term is absent when there is no word match. Candidates come from the
top twelve entries of either ranking. One slot can retain the strongest word
match when fusion would otherwise drop it. That is an evidence-selection
heuristic, not proof that the passage answers the question.

`RetrievalHit.score` remains cosine similarity for compatibility. The separate
developer trace records BM25, RRF, routing and selected IDs. None is a
probability that the answer is true. We do not use a similarity threshold as a
claim verifier.

This is semantic retrieval **inside discussion RAG**. Movie discovery continues
to use keyword/title/person search as requested.

## When does section routing help?

An explicit event cue such as `claim`, `ending` or `story` can focus a classified
article on Plot. A theme, interpretation, filmmaking or mixed question keeps the
whole eligible article. For example, asking what Batman's sacrifice represents
must still reach thematic analysis.

The rule uses English words, not movie names or IDs. It is deliberately limited:
unusual wording can be misclassified. Unclassified learning fixtures retain the
broader behavior; a classified article with no eligible Plot passage cannot
silently substitute production commentary for an event.

Movie/spoiler/model/vector checks happen before routing. Topic filtering must
never hide an invalid embedding or authorize another movie's evidence.

## Why change the model's response format?

The public response still contains an answer and citations. Internally the model
now returns:

```json
{
  "status": "answered",
  "answer": "To lure the Joker out.",
  "evidence_quotes": ["A verbatim excerpt offered by code"]
}
```

The example is illustrative; an actual excerpt must be in the offered options.
Long passage IDs stay private to code. Sentence options reduce adjacent text;
a bounded full-window option keeps relevant context when character chunking
cuts a sentence. All choices retain original source text.

Schema-constrained generation is a decoding aid. We also show the choices in
the prompt so the model can reason about them, then validate membership in
Python. A schema alone does not explain the task or replace validation.

Earlier attempts are retained in the reports: short ID aliases still selected
wrong sources; free-text quotes introduced punctuation changes, ellipses and
truncation. Offered excerpts avoid those copying errors. Repeated valid excerpts
normalize to one citation. Invented/unoffered text, inconsistent status and
oversized responses still fail validation. There are no extra model retries.

**A real quote can still be irrelevant.** Exact quote presence proves location,
not that the quote entails the answer. The development inspection therefore
records both the selected support text and the full cited passage. Valid-looking
JSON and a source link are not enough to call an answer verified.

## What the evaluations measure

The comparison uses seventeen fixed development cases across The Dark Knight,
Arrival and Knives Out, including three questions requiring abstention. The
original five labels remain unchanged. The twelve additions were source-inspected
by the assistant before their first model outputs; they are not independent
human labels. Repeated tuning has consumed them as development data.

The archived baseline keeps its old vector-only pipeline and full-ID prompt.
Both arms use the same movie revision, chunks, labels and local models. Calls
run sequentially and alternate order. This compares the complete pipeline
change; it does not isolate retrieval from generation or compare multiple agents.

Read [the comparison inspection](../../evals/movie-rag/coverage/discussion-retrieval-review.json)
for counts, actual failures and assistant review. Automated checks measure:

- Whether top-three retrieval contains an annotated supporting passage.
- Expected answer/abstention status, required phrase groups and citation IDs.
- Validation failures and observed duration.

Labels are incomplete and phrase checks can reject supported paraphrases. Keep
the original failure and document the limitation; do not rewrite expectations
after seeing an answer to claim improved accuracy. Conversely, an automated
pass can contain irrelevant quoted text or extra citations.

The six separate grounding cases exercise fixed evidence, missing evidence and
two injection examples. They do not measure live retrieval, tool authorization
or every attack. Deterministic tests verify code boundaries and error handling;
their pass count is not a model-quality percentage.

## Limits and next work

Discussion still uses one query embedding and at most one chat call per question.
Cached source embeddings are reused. The model has no executable tools or
authority to fetch arbitrary URLs, publish banks or alter user collections.

These changes do not qualify automatic publication or change script-assisted
story gates. All eleven saved banks and Inception's existing more-question gate
are preserved. More dependable claim-to-evidence verification, sentence-aware
discussion context and fresh independent labels remain needed. Warm local
durations are observations, not multi-user throughput or deployment benchmarks.

For reproduction, see the [coverage README](../../evals/movie-rag/coverage/README.md).
The original source snapshots are private local artifacts; changed revisions
require newly inspected labels.
