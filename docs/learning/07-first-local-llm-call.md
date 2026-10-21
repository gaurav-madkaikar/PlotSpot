# Lesson 07 — your first local LLM call

## Ownership and learning rhythm

You own the AI pipeline: model calls, embedding inputs, chunking, retrieval, grounded prompts, answer validation, and eventually agent state/tool choices and evaluation experiments. I own the UI, routes, persistence plumbing, connector scaffolding, failure-state integration, and review. We write and test one understandable slice at a time. I will not quietly fill in your assigned functions.

For each slice: explanation → worked example → your implementation → focused checks → review and answers → integration into Frame. Passing tests verifies behavior, not complete understanding; explain the flow in your own words too.

## First, your cosine review

Your dot product and magnitude formula pass all five ordinary-vector cases. Six edge cases still fail. In `vector_math.py`:

1. Before calculating, reject an empty list or different list lengths with `ValueError`. `zip([1], [1, 2])` yields only `(1, 1)`; it doesn't report the missing coordinate.
2. Check each coordinate with `math.isfinite`. `NaN` and infinity can propagate into scores without raising an error.
3. After calculating the norms, return `0.0` if either is zero. Dividing by their product otherwise raises `ZeroDivisionError`.

These guards are important because retrieval must not silently rank malformed embeddings. Keep your correct formula underneath them.

## The big picture

There are two related paths:

```text
Movie discovery:
movie descriptions → embeddings → catalog index
user description → embedding → hard filters → similarity ranking → movie tiles

Grounded movie discussion / RAG:
approved sources → passages with provenance → embeddings → evidence index
question + movie ID + spoiler permission → retrieve eligible passages
→ build prompt with evidence IDs → local LLM → validate answer/citations → UI
```

Embeddings produce vectors; a chat model produces text. Semantic search can return films without generating any answer. RAG adds a generation step using retrieved evidence. A vector database is an index for finding evidence; it doesn't make that evidence accurate or trustworthy.

We will begin retrieval with a tiny, explicitly synthetic teaching dataset so you can inspect every result. Then we will connect attributed movie sources. Synthetic teaching text will not be presented as real movie reporting.

## What happens in a model call?

Our Python code is a client. Ollama is a separate local process serving HTTP on port 11434. Ollama loads the requested model, runs inference, and returns a response. No cloud inference key is needed for this local exercise.

A worked example with a different endpoint:

```python
import asyncio
import httpx

async def inspect_models():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=10,
        trust_env=False,
    ) as client:
        response = await client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [entry["name"] for entry in data["models"]]

print(asyncio.run(inspect_models()))
```

- `async def` defines a coroutine. Calling it creates work that must be awaited or run by an event loop.
- `async with` opens and reliably closes the HTTP client, including when an error occurs.
- `await client.get(...)` lets the event loop do other work while it waits for the response. It does not automatically create parallel model calls.
- `raise_for_status()` converts unsuccessful HTTP status codes into exceptions.
- HTTPX `response.json()` is synchronous: the response body has already arrived. This differs from browser `fetch`, where reading `response.json()` returns a promise.
- The base URL identifies Ollama; the endpoint selects the operation. Timeouts prevent waiting forever.

Ollama was checked on 2026-10-08: `llama3.2:3b` and `qwen3.5:9b` are installed. Use `llama3.2:3b` for this first exercise. We have not yet checked/downloaded an embedding model or benchmarked answer quality.

## Your implementation

Implement only `chat_once` in `backend/src/movie_companion/ollama_learning.py`.

1. POST to `/api/chat` using the supplied client.
2. Send the chosen model, one user message containing `prompt`, and `stream: false`.
3. Call `raise_for_status()` before reading successful response data.
4. Extract `message.content` and require a nonempty string after trimming whitespace. Raise `ValueError` when that content is missing or invalid.
5. Return the text. Let HTTP errors propagate; don't turn failures into invented answers.

Example request body (replace the sample values with function arguments):
```json
{
  "model": "llama3.2:3b",
  "messages": [{"role": "user", "content": "Explain an embedding briefly."}],
  "stream": false
}
```

Simplified response shape, with illustrative text rather than an observed reply:
```json
{
  "message": {"role": "assistant", "content": "An embedding represents text as numbers."},
  "done": true
}
```

`stream: false` asks for one complete JSON response. Streaming is a later UI enhancement; its response framing requires different parsing. See the official [chat endpoint](https://docs.ollama.com/api/chat), [model listing](https://docs.ollama.com/api/tags), and [embedding endpoint](https://docs.ollama.com/api/embed).

## Run the checks

From `backend`:

```sh
.venv/bin/pytest tests/test_vector_math.py tests/test_ollama_learning.py -q
```

The seven new chat checks use a fake HTTP transport. They check your request payload, response parsing, and failure behavior without loading a model. They intentionally fail against the starter stub. The running app does not call this stub, so discovery remains usable.

Once those checks pass, try actual local inference:

```sh
.venv/bin/python scripts/try_local_chat.py
```

The first request may take longer while the model loads. If you get a connection error, check whether Ollama is running. A successful reply proves connectivity and parsing, not factual accuracy or RAG grounding. We will review your code before promoting this helper into the application client.

## Questions to discuss after your implementation

1. Why do we await the HTTP request but not HTTPX `response.json()`?
2. What changes when `stream` is true?
3. Why is an HTTP 200 response insufficient to trust its content?
4. How is a chat reply different from an embedding?
5. Why is this model call not yet an agent or a RAG system?

## Completed review — 2026-10-09

Your corrected request, HTTP status handling, nested content extraction, string validation, and whitespace check passed all seven original chat tests. Your cosine implementation also passed all 11 vector checks. The whole backend suite passed 73 cases before assistant extensions.

The assistant removed an unused Pydantic import and the response-object debug print, formatted the request, and added checks that the top-level JSON and `message` are dictionaries. Without those checks, `{"message": null}` or a top-level JSON array would cause an attribute error instead of the promised `ValueError`. Three new malformed-response cases were added; all 76 backend cases passed afterwards.

The local smoke script succeeded with `llama3.2:3b`. It returned two sentences explaining embeddings as numerical representations of text. Its “unique fingerprint” analogy is useful only as an approximation: embeddings do not guarantee uniqueness or exact semantic equivalence. A working model call does not make every generated explanation correct.

The helper remains disconnected from public app routes. We have verified a real local chat request, not movie RAG or an agent.

## Your completed flow

1. The script opens the local client with a timeout and gives it to `chat_once`.
2. Your function builds the JSON payload and awaits the POST. Ollama runs the chosen model.
3. HTTP errors propagate through `raise_for_status()`; successful JSON is parsed locally.
4. The envelope and nested message are checked before accessing content.
5. Your type check runs before `.strip()`, then your empty-content check runs before returning the answer.
6. The script prints the answer and closes the client. Tests supply a fake client through the same interface.

## Answers to the review questions

### 1. Why await the request but not HTTPX response.json()?

The network request can take time, so HTTPX's async client exposes it as an awaitable operation. By the time a non-streaming request returns, HTTPX has read the response body. `response.json()` parses those already available bytes synchronously. Browser `fetch` has a different API, where reading the body is asynchronous too.

### 2. What changes when stream is true?

Ollama returns a sequence of JSON objects as generation progresses. You need streaming iteration and per-object parsing, then collect or display content increments until completion. Calling `.json()` once on the entire stream is not the same operation as parsing one non-streaming reply. We begin without streaming to make the request and validation easier to inspect.

### 3. Why is HTTP 200 insufficient to trust content?

It establishes that the HTTP operation succeeded. The body can still have the wrong shape, missing/empty text, an unsupported factual claim, or an answer to the wrong question. Shape/type validation and factual grounding solve different problems. Our helper handles the former; RAG and answer evaluations will address the latter.

### 4. How is a chat reply different from an embedding?

A chat model generates readable text. An embedding model produces a numeric vector for comparison and retrieval. The same question could become a vector to locate relevant evidence, then become a message in a chat prompt alongside that evidence. Neither operation automatically performs the other.

### 5. Why is this not yet an agent or RAG?

The helper performs a fixed model request. It doesn't retrieve external passages or provide them as evidence, so it is not RAG. It also doesn't decide which tools to use or run an observation/decision/action loop, so it is not an agent. Those capabilities will be added explicitly and tested separately.
