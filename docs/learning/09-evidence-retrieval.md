# Lesson 09 — find evidence before asking the LLM

## Where this fits

You have written the local chat call, embedding call, and cosine similarity. Now use those vectors to choose passages that might answer a question. This is the retrieval part of RAG. We start with a small in-memory list so you can inspect everything; no LangChain or vector database is needed yet.

```text
Authored passages → embed_texts → passage records with vectors
Question → embed_texts → query vector
                         ↓
Filter eligible records → your ranking function → top-k evidence
                                                 ↓
Later: question + evidence → chat_once → cited answer
```

This exercise returns evidence, not a generated answer. The learning script is disconnected from the webpage. After retrieval and grounded generation work, we will connect that pipeline to the selected movie's backend endpoint and frontend panel.

## Why store records rather than just vectors?

An `EmbeddedPassage` keeps the vector alongside its text, passage ID, movie ID, source label, embedding model, and spoiler status. A score without this information cannot tell us what to quote, which movie it belongs to, or how to attribute an answer.

`@dataclass` provides a constructor for these named fields. You access fields with a dot, such as `passage.vector` or `passage.text`. It is a Python record, not an AI framework. Type annotations describe expected types; they do not validate incoming JSON. `frozen=True` prevents assigning a new value to a field, but does not make the vector list itself immutable. Treat supplied records and vectors as read-only.

`RetrievalHit` wraps a passage and its score:

```python
# Illustrative construction once you have a passage and calculated a score:
hit = RetrievalHit(passage=some_passage, score=0.72)
print(hit.passage.text)
print(hit.score)
```

Keep the original passage object. Do not return only a score or replace its text with a summary. Later, the same passage ID and source metadata will support citations.

## Your coding slice

Implement only `rank_passages` in `backend/src/movie_companion/retrieval_learning.py`. Replace its `NotImplementedError`.

1. For each passage, calculate `cosine_similarity(query_vector, passage.vector)` and create a `RetrievalHit` containing the passage and score.
2. Sort the hits by highest score first. When scores tie, use `hit.passage.passage_id` in ascending order.
3. Return the first `k` hits. If fewer exist, return those available; do not pad or duplicate results.

The assistant-owned `retrieve_passages` wrapper validates vectors, matching model/dimensions, unique evidence IDs, and `k`. It restricts evidence to the requested movie and filters spoilers **before** calling your function. You do not need to write validation branches in this exercise.

Use a new list for the scores and `sorted(...)` to avoid rearranging caller-owned inputs. Keep negative similarities; they are not probabilities and should not be converted to percentages or clipped to zero.

## Python patterns to help you

Appending objects follows the same pattern as appending strings:

```python
labels = []
for name in ["first", "second"]:
    labels.append(name.upper())
```

Sorting descending on one field and ascending on another:

```python
entries = [("orange", 5), ("apple", 5), ("pear", 8)]
ordered = sorted(entries, key=lambda entry: (-entry[1], entry[0]))
# [("pear", 8), ("apple", 5), ("orange", 5)]
```

The negative numeric key puts larger scores first, while the second key breaks ties alphabetically. `lambda` is a small function that tells `sorted` which values to compare. In your exercise, read fields from each hit rather than using tuple positions.

Slicing takes up to the requested number of items:

```python
numbers = [10, 20, 30]
numbers[:2]  # [10, 20]
numbers[:5]  # [10, 20, 30]
```

The `*` in the function signature makes `k` a keyword argument: call with `k=2`. Your ranking function is synchronous because it calculates and sorts values already in memory. The surrounding script is asynchronous because embedding requires HTTP requests to Ollama.

## Worked example — invented vectors

For query `[1, 0]`, these three passages have cosine scores:

| Passage ID | Vector | Score |
|---|---|---:|
| a | [0, 1] | 0 |
| b | [1, 0] | 1 |
| c | [1, 1] | approximately 0.7071 |

For `k=2`, return hits for `b`, then `c`, retaining their passage records. These are made-up vectors that expose the mechanics, not real model outputs.

## Run the exercise

From the project's `backend` directory:

```sh
.venv/bin/pytest tests/test_retrieval_learning.py -q
```

At the starter checkpoint, there are 16 cases: 11 assistant-owned boundary cases pass, while five ranking cases fail because your function is unfinished. Once implemented, all 16 should pass. These tests use invented vectors and need no running LLM. The full backend suite includes this exercise, so it will also contain the five intentional failures until you finish it.

After implementing ranking, run the local example with Ollama running and your existing `nomic-embed-text:v1.5` model:

```sh
.venv/bin/python scripts/try_local_retrieval.py
```

The script embeds four **fictional** cinema-programme notes and a question about spacecraft sound production. It preserves text/vector order with `zip`, and uses the model-specific `search_document:` and `search_query:` prefixes explained in lesson 08. It then retrieves two passages for the fictional movie Orbit Day.

The other movie's sound note and the spoiler-labelled ending are excluded before ranking. Inspect whether the production sound note ranks above the costume note. Do not hardcode that result: the test of your algorithm and the quality of a model's ranking are different questions.

## What is stored, and what is still missing?

For this demonstration, the passages and vectors exist in a Python list for one script run. Each run embeds them again. There is no persistent index or embedding cache. A later vector database will store the records and vectors and let us search them across requests without repeating every document embedding. It does not eliminate the need for source attribution, model/version consistency, or movie/spoiler filtering.

We deliberately use pre-split passages here. Later ingestion will split longer articles into chunks, record their source and revision, and persist embeddings. Real news and interview connectors come after this mechanical exercise; the fictional notes are not movie facts.

Top-k means “the best available k,” not “k relevant sources.” An unrelated question can still produce hits. We will evaluate retrieval quality and introduce grounded abstention before exposing answers in the app. Similarity cannot establish that a claim is true. Filtering on spoiler labels also depends on correct labels; it is one boundary, not a complete safety system.

## Concepts to explain afterwards

1. Why retain passage IDs and source labels in each retrieval hit?
2. Why does returning top-k not prove the evidence answers the question?
3. Why filter other movies and spoilers before ranking and generation?
4. Why use passage IDs to break equal-score ties?
5. What changes when we replace the in-memory list with a vector database, and what responsibilities remain?

We will record answers and measured results here after reviewing your implementation. Existing app behavior and movie routes remain unchanged at this checkpoint.

## Completed review — 2026-10-09

Your implementation calculates cosine scores, stores `(-score, passage_id)` tuples, sorts them, selects the first `k`, then restores positive/negative original scores when constructing the hits. The ID-to-passage dictionary retains the original evidence objects. This works because the wrapper rejects duplicate eligible IDs before ranking. Sorting the newly created tuple list with `.sort()` is safe here: it does not rearrange the caller's passage list.

All 16 retrieval cases and all 111 backend cases passed. The real local `nomic-embed-text:v1.5` example returned:

| Passage | Score |
|---|---:|
| Sound-production note | 0.7641 |
| Costume-production note | 0.5983 |

The other movie and spoiler ending were excluded. The relevant note ranked first, but the unrelated costume note was still returned because `k=2`. This is a small fictional example, not a retrieval-quality benchmark or calibrated relevance threshold. No generated answers or app integration were added.

One optional simplification: `{passage.passage_id: passage for passage in passages}` already produces a dictionary, so wrapping it with `dict(...)` makes an unnecessary copy. Your code was left unchanged; the current algorithm is correct under the wrapper's input contract. You could also store hits directly to avoid the extra ID lookup, but that is a readability choice rather than a correctness fix.

## Answers to the review questions

1. **Why retain IDs and sources?** We need to trace an answer back to its evidence, display source attribution, and distinguish passages even when their text is similar. A similarity score alone has no provenance.
2. **Why is top-k not proof of relevance?** Ranking compares candidates against one another. Even if none answers the question, some still rank highest. A similarity score is neither a truth check nor a probability of correctness; evaluation and grounded abstention are separate responsibilities.
3. **Why filter before ranking and generation?** Another movie's passage can be semantically similar but wrong for the selected film. Spoiler passages must not reach the answer prompt when permission is absent. Filtering first also prevents excluded records from consuming top-k slots. Correct spoiler labels remain necessary.
4. **Why break ties by ID?** Equal scores otherwise depend on input order. A stable secondary key makes results reproducible when ingestion order changes, helping tests, debugging, and comparison across runs.
5. **What changes with a vector database?** Records and vectors persist across requests, and a suitable index can search larger collections efficiently. Query embedding, compatible model versions, movie/spoiler filtering, source provenance, retrieval evaluation, and answer grounding still matter. Metadata filters must be enforced before evidence reaches generation.
