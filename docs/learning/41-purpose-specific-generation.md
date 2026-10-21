# 41. Separate evidence before asking the model to generate

In the previous mixed-evidence run, the model received two story passages and two production passages in one prompt. It produced two useful-looking facts but also two production-trivia questions. Our deterministic purpose checks rejected those quiz proposals. Instructions alone did not maintain the distinction.

The generator now makes two small, sequential calls: facts from background evidence, then quiz questions from story evidence. This uses ordinary async Python and JSON schemas, without LangChain.

## What changed in the code

`content_proposal_learning.propose_content` retains its existing public API. It validates all evidence, partitions it by purpose, calls `_propose_branch` for each nonempty group and returns one `ContentProposals` object.

For example, given story passages `P1`, `P2` and background passages `P3`, `P4`:

| Call | Evidence supplied | Allowed output |
|---|---|---|
| Fact generation | P3, P4 | At most two facts; questions must be empty |
| Quiz generation | P1, P2 | At most two questions; facts must be empty |

The original source aliases remain intact so the existing provenance checks and critic can use the merged result without remapping citations. A movie title and instructions remain input too; separating evidence does not erase the model's internal knowledge. It must still use only the supplied source for claims.

## Three layers enforce the boundary

**Input isolation:** The fact request never contains story passages, and the quiz request never contains background passages. The prompts focus on one task each.

**Schema constraints:** The active branch permits two items and restricts passage IDs to its evidence group. The other array has `maxItems: 0`. Qwen receives this JSON schema through Ollama's structured response format.

**Python checks:** After parsing, the backend checks that the inactive array is empty, the active array has at most two items, and every reference belongs to the branch. These checks reject a model reply even when it ignores the schema. Existing quote, source-section, duplicate and semantic review checks remain downstream.

A quiz question can still be wrong, subjective or use weak distractors even when it cites a story passage. The new boundary solves an input-routing problem; it does not prove semantic correctness.

## Why the calls are sequential

The implementation uses an ordinary loop with `await`:

```python
for purpose, key in [('background', 'facts'), ('story', 'questions')]:
    branch = [p for p in passages if p.purpose == purpose]
    if branch:
        results[key] = await _propose_branch(
            client, model=model, movie_title=movie_title.strip(),
            passages=branch, purpose=purpose,
        )
```

`await` waits for one local model response before starting the next call. This avoids competing inference requests on the same laptop. Independent responsibilities do not require parallel execution. The architecture can change its scheduling later if hardware and measurements justify it.

If only story evidence exists, fact generation is skipped. An empty array is a valid abstention. There is no automatic retry.

## Budgets and failure behavior

A mixed batch now uses two generator calls and one baseline critic call; the optional structured critic can use two review calls. At eight batches, the maxima are sixteen generator calls plus eight baseline critic calls, or sixteen structured critic calls. Each generator branch has a 1,536-token output ceiling. The overall preparation deadline remains at most 600 seconds, including retrieval.

If the second generator call fails, the current batch does not return a partial proposal bundle for review. Previously completed batches remain in the preparation checkpoint. The first branch of the failed batch is not independently checkpointed. Per-branch recovery is a later improvement, not silent retry behavior.

Generation policy `movie-purpose-generation-v2` is recorded in new preparation reports. Subsequent reports also include its source-file fingerprint and generation branch names for completed batches. The earlier combined implementation is retained as `evals/movie-rag/policies/movie-combined-generator-v1.py.txt` for interpreting historical runs.

## Tests and practical limits

Transport fixtures check that each request contains only its evidence, has the correct aliases and array limits, and occurs sequentially. They also test absent branches, empty responses, foreign aliases, extra items, cross-branch results and a failed second call. The critic remains a separate stage.

These tests verify contracts. Real Ollama runs verify integration. Neither is a representative quality benchmark. Future evaluation needs a fixed labelled movie-source set and repeated comparable runs to distinguish consistent behavior from sampling variation.

## Questions and answers

**Are these two agents?** They are two specialist generation roles with separate contexts and contracts. Calling them agents does not change the engineering; they currently have no tool loop or independent planning. Preparation coordinates retrieval, generation and critique.

**Why keep both facts and questions fields in each reply?** It preserves the shared return contract and existing parsing. The inactive field must be empty. A separate branch response type would also work, but is not required for this boundary.

**Can the model cite a passage from the other call?** Such a response fails the branch's schema hint and the explicit Python alias check. The full evidence checker still runs afterward.

**Will this eliminate production trivia questions?** It removes production passages from quiz inputs and prevents background aliases in quiz output. It cannot eliminate every incorrect claim or a production question hallucinated against a story quote. Evidence and semantic checks are still necessary.

**Will these drafts immediately appear on the movie page?** No. The preparation command writes draft reports. The app continues serving the reviewed saved collections. Visible progress and draft review are subsequent integration work.

## Actual local result

The one-batch Inception run used exactly the same four evidence records as the earlier mixed-generator run, verified by comparing the full records. It took **43.66 seconds** and produced two fact proposals and two story-question proposals. All four passed the necessary source-purpose/quote checks. The previous run's two quiz proposals had failed the purpose checks because they cited production passages.

The critic accepted both new facts but rejected both story questions, so the saved draft report contains **two retained facts and zero retained questions**. It is incomplete because a single batch cannot meet five facts and ten questions. Nothing was published.

One generated question asks what job Saito offers Cobb; the source establishes implanting the idea that Fischer should dissolve his father's conglomerate. The critic's rejection says distractors describe things other than that objective. Incorrect distractors alone are expected, so this reasoning does not establish a real flaw. The other question asks what Saito promises Cobb; one option is implausible and another potentially overlaps with the correct option. Its rejection may be warranted, but the critic's explanation does not clearly identify those problems.

The first fact also combines camera details about an unspecified sequence with the Paris folding scene under a Paris-focused title. This risks implying a link the excerpt does not establish. Critic acceptance does not resolve that ambiguity.

These observations are preserved in `evals/movie-rag/purpose-generation-observations.json`, alongside the exact generator fingerprint and unchanged input comparison. The complete trace is `preparation-inception-purpose-branches-one-batch.json`; the generator implementation is archived as `policies/movie-purpose-generator-v2.py.txt`. No claim of a general quality or speed improvement follows from one run.

**581 backend checks passed.** Frontend and reviewed app collections remain unchanged. Next: visible preparation state and draft inspection; critic explanations and semantic quality remain limitations, and automatic publication stays gated.
