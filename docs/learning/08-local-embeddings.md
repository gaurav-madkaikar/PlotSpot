# Lesson 08 — text becomes a vector

## Where this fits

You have written a working local chat call and cosine similarity. Next you will write an embedding call. After that, you will implement retrieval, then pass retrieved evidence into your chat prompt. No LangChain, vector database, or new Python package is needed for this lesson.

```text
This lesson: text → embedding model → vector → cosine comparison
Next lesson: question vector + stored passage vectors → relevant passage IDs
Later: question + retrieved passages → chat model → cited answer
```

## Embeddings explained with a small example

Imagine comparing these descriptions:

- A reflective story about astronauts exploring distant planets.
- A comedy about a chaotic family dinner.
- A detective mystery in a small town.

For “a thoughtful film about exploring space,” the first description is a sensible relevant candidate, even though it does not contain the exact phrase. An embedding model maps descriptions and the query into numeric vectors so we can compare them.

Invented two-dimensional vectors make the mechanics visible:

```python
query = [1.0, 0.0]
space_story = [0.9, 0.1]
family_comedy = [0.1, 0.9]
```

Your cosine function scores the space vector higher. These numbers are teaching examples, not real model outputs. Real coordinates are learned jointly and are not individually labeled “space” or “comedy.” Similarity is a retrieval signal, not a probability that an answer is correct.

## The API difference

| Operation | Endpoint | Main input | Main output |
|---|---|---|---|
| Chat | `/api/chat` | `messages` | `message.content`: text |
| Embed | `/api/embed` | `input` | `embeddings`: list of vectors |

Ollama accepts a text or list of texts in `input`; our helper consistently uses a list. Even one text produces a nested list. We use `truncate: false` so oversized inputs cause an error instead of being silently cut off. See the [official embedding API](https://docs.ollama.com/api/embed).

Example request:

```json
{
  "model": "nomic-embed-text:v1.5",
  "input": ["search_document: A journey through space."],
  "truncate": false
}
```

Simplified illustrative response, using three made-up coordinates:

```json
{"embeddings": [[0.12, -0.41, 0.85]]}
```

The outer list represents inputs. Each inner list is one input's vector. Preserve the correspondence between text index and vector index.

## Model setup

Ollama was checked on 2026-10-09: only `llama3.2:3b` and `qwen3.5:9b` were listed. Those are our installed chat models; the embedding model has not been downloaded by the assistant.

When you are ready for the real-model experiment, run:

```sh
ollama pull nomic-embed-text:v1.5
```

The [official Ollama model listing](https://ollama.com/library/nomic-embed-text:v1.5) lists approximately 274MB. This download needs internet once; inference uses your local Ollama service. The unit tests need neither a download nor a running model.

For this model, use `search_document: ` before indexed text and `search_query: ` before a user's question. These are model-specific task instructions, not universal rules for every embedding model. Our helper sends caller-supplied text unchanged; the demo script supplies the prefixes. See the [Nomic model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).

## Your coding slice

Implement `embed_texts` in `backend/src/movie_companion/embedding_learning.py`. Keep using the supplied client, as you did in `chat_once`.

1. Reject an empty input list or any element that is not a nonblank string with `ValueError`, before a network call.
2. POST JSON to `/api/embed`, with `model`, `input: texts`, and `truncate: False`. There is no chat `messages` field or `stream` field in this exercise.
3. Call `raise_for_status()` and parse the JSON. Let HTTP errors propagate.
4. Require a dictionary with an `embeddings` list. Its length must equal the number of inputs.
5. Require each vector to be a nonempty list, with the same dimensions as the others. Don't hardcode a dimension count: the fake tests use two coordinates, and the actual model returns more.
6. Require every coordinate to be a finite number. Reject booleans explicitly: Python treats `bool` as a subclass of `int`.
7. Reject an all-zero vector: it carries no direction for useful retrieval. This is stricter than our cosine helper, which safely returns zero for a zero vector.
8. Return the validated vectors in their original order; do not sort them by value.

## Useful Python patterns — separate examples

Checking lengths:

```python
names = ["first", "second"]
results = [10, 20]
if len(names) != len(results):
    raise ValueError("One result is required per name")
```

Traversing a nested list:

```python
rows = [[0.2, 0.8], [0.7, 0.3]]
for row in rows:
    print("Dimensions:", len(row))
    for coordinate in row:
        print(coordinate)
```

For numeric validation, use `isinstance(value, (int, float))` and `math.isfinite(value)`, after rejecting booleans. For a zero vector, ask whether **any** coordinate is nonzero. Nested validation is ordinary Python; it doesn't require AI libraries.

## Check your implementation

From `backend`:

```sh
.venv/bin/pytest tests/test_embedding_learning.py -q
```

There are 19 checks: batch/single requests, HTTP errors, malformed vectors, and invalid inputs. They intentionally fail until you implement the helper. They use `MockTransport`, so they are testing the API contract, not embedding quality. This stub is disconnected from the app; discovery remains usable, but the complete backend suite includes the intentionally failing exercise.

Once the checks pass and the model is installed:

```sh
.venv/bin/python scripts/try_local_embeddings.py
```

The supplied script embeds three invented descriptions and a query, then calls your cosine function. It prints each score beside its description without selecting a movie or generating an answer. Observe whether the space description scores highest; if it doesn't, investigate rather than hardcoding the expected result. This tiny demonstration is not a quality benchmark.

## Explain afterwards

1. Why does a single input still return `list[list[float]]`?
2. Why must query and document vectors use the same embedding model?
3. Why do we reject zero vectors here when cosine safely handles them?
4. Why is preserving input/output order important?
5. What does this exercise prove, and what does it not prove about RAG?

## Completed review — 2026-10-09

You implemented the embedding API request and response parsing. You then asked to focus on API calls and main AI business logic, with the assistant handling checks. The assistant completed empty-input rejection, finite-number/boolean validation, and independent zero-vector rejection. An individual zero coordinate is valid; an entirely zero vector is not useful for retrieval. All 19 embedding checks and all 95 backend checks pass.

The user-installed model returned three vectors of 768 dimensions. In the supplied synthetic experiment, the query's cosine scores were:

| Description | Score |
|---|---:|
| Reflective space exploration | 0.7604 |
| Family holiday comedy | 0.6215 |
| Small-town detective mystery | 0.5751 |

The expected relevant description scored highest. The numbers are similarities, not confidence percentages. The unrelated comedy still scored above 0.6, which illustrates why we must measure retrieval behavior before choosing an abstention threshold. One synthetic query establishes neither broad retrieval quality nor a reliable threshold.

## Answers to the review questions

1. **Why a nested list for one input?** The endpoint supports batches and uses a consistent response structure. `vectors[0]` is the first text's vector, while `vectors[0][0]` is its first coordinate.
2. **Why the same model?** Query and document vectors must inhabit the same learned coordinate space. Identical dimensions alone do not make vectors from different models comparable. Prefix handling and model/input versions must also remain consistent.
3. **Why reject zero vectors here?** Cosine's zero fallback avoids a crash, but ingesting a zero vector would conceal an unusable representation. Validate it at the embedding boundary so retrieval can distinguish invalid data from a genuinely low similarity.
4. **Why preserve order?** The caller associates each vector with the corresponding input's text and identity. Reordering vectors would attach scores to the wrong passages or movies. Sorting happens later on scored records that retain their IDs.
5. **What is proven?** Contract tests verify request/response handling. The real experiment verifies local inference and vector comparison for one small example. It does not test persistent indexing, top-k retrieval, chunk quality, grounding, citations, spoiler enforcement, or agents.

Persistent indexes, chunking, and top-k retrieval come next. Under the updated ownership, your next exercise will focus on retrieval logic while the assistant supplies its validation and tests.
