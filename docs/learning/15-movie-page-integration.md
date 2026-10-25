# Apply your RAG helpers to the movie page

This is the actual app integration milestone. You have finished the separate foundation exercises. Your next function connects the helpers you wrote to the movie page; you do not need another library or LangChain.

## Follow one question through the app

```text
Interstellar page → Discuss → Your question → Ask Frame
  frontend/src/components/movie-question-panel.tsx
           ↓ askMovie sends a POST JSON body
  frontend/src/lib/api.ts
           ↓ /api/movies/157336/questions
  backend/src/movie_companion/main.py
           ↓ input validation and service call
  movie_questions.py: permission → source → ingest/load evidence
           ↓ your function
  movie_qa_learning.py: query embedding → retrieval → grounded answer
           ↓ verified citation IDs mapped to source excerpts and revision links
  JSON response → Zod validation → React displays answer and expandable sources
```

The service already handles deadlines, busy requests, source caching, persistent evidence, error responses and citation links. You own `answer_movie_question` in `backend/src/movie_companion/movie_qa_learning.py`. **Completed on 2026-10-10:** this function now connects the endpoint to your embedding, retrieval and grounding helpers. The instructions below remain as a reference.

## Your coding slice

Compose three existing helpers; do not rewrite their internals.

1. Await `embed_texts` with the supplied client, `model=embedding_model`, and a one-item `texts` list containing `f"search_query: {question}"`.
2. Select the first returned vector. Even for one question, the embedding API returns a list of vectors. For example, `[[0.2, 0.8]]` means the query vector is `[0.2, 0.8]`.
3. Call `retrieve_passages` with that vector and `passages`. Supply `query_model=embedding_model`, `movie_id=movie_id`, `allow_spoilers=allow_spoilers`, and `k=3`.
4. Await `answer_from_hits` with the supplied client, `model=chat_model`, `question=question`, and your retrieved `hits`. Return its `GroundedAnswer` directly.

The embedding and answer helpers perform HTTP requests and need `await`. Retrieval performs local calculations and returns immediately; it does not need `await`.

A smaller example of composing async helpers:

```python
async def summarize_saved_notes(client, notes):
    prepared = clean_notes(notes)          # ordinary local function
    summary = await summarize(client, prepared)  # waits for remote response
    return summary
```

Use the two supplied model names for their different jobs. Document ingestion uses `search_document:`; the question uses `search_query:`. The document vectors and query vector must use the same embedding model.

## Verify your function

From `backend`:

```sh
.venv/bin/pytest tests/test_movie_qa_learning.py -q
```

This test uses authored evidence and mocked Ollama HTTP responses. It checks the query prefix, the embedding-before-chat order, inclusion of retrieved evidence, and the returned citation ID. It does not measure real-model answer quality. The assistant has run broader checks and a real end-to-end question after reviewing your function.

For a manual app run, start Ollama with the already installed `nomic-embed-text:v1.5` and `llama3.2:3b` models, then start the existing backend and frontend:

```sh
# Terminal 1, from backend
.venv/bin/uvicorn movie_companion.main:app --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2, from frontend
npm run dev
```

Open `http://127.0.0.1:5173/movies/157336`, enable **Watched — allow spoilers**, open **Discuss**, and ask a question. A useful first question is “Who composed the music for Interstellar?” The first request fetches and embeds the article; later requests can reuse its stored vectors. Questions still require fresh query embedding and generation. Your completed function now produces live answers in this UI.

## What is cached here?

- **Source:** the service keeps the fetched article in memory for five minutes. A backend restart clears this cache.
- **Document evidence:** Chroma persists chunks and vectors under `data/chroma/app`. Source content/revision, model tag and chunk settings identify a snapshot. An unchanged snapshot avoids repeating document embeddings after a restart.
- **Answers:** this first panel does not cache generated answers. It holds one answer in React state and clears it when the movie or spoiler preference changes.

Cancellation stops the browser waiting and prevents a late response from appearing. It does not guarantee that already running backend/model work stops; the server's job limit and deadline still apply.

## Scope and evaluation

Only Interstellar has a reviewed source mapping. Wikipedia is an attributed background source, not the planned external movie-news feed. Whole-article content has unknown spoiler status, so permission is required before any source/model request. Model output is plain text with validated citation IDs; links come from the service's source record. The model cannot browse or execute actions in this milestone.

Existing six-case grounding evaluations remain available. API/browser tests verify wiring and boundaries, while retrieval relevance and claim support on real movie questions need a separate labelled set. Real outputs are recorded below; a labelled movie evaluation set comes before expanded coverage and parallel agents.


## Completed review and real app result — 2026-10-10

Your composition was correct. The assistant corrected two retrieval-call arguments: `top_k=3` became `k=3`, and `query_model=embedding_model` was supplied. Python keyword names must match the called function's signature; names that mean similar things are not interchangeable. The model check prevents comparing vectors from different embedding models even if their dimensions happen to match. Your API-call and generation flow was retained.

All **201 backend tests pass**, including the formerly pending app-pipeline case. The preceding integration's 18 browser checks and production build passed; this review additionally ran a real browser request without mocked providers.

| Real request | Observed result |
|---|---|
| Composer question without spoiler permission | `spoiler_permission_required`, no citations |
| “Who composed the music for Interstellar?” with permission | “Hans Zimmer composed the music for Interstellar.” with revision-linked evidence |
| Same question again | Same supported answer; first and repeat endpoint runs took 11.50 and 1.87 seconds |
| “What did I write in my private diary after watching Interstellar?” | `insufficient_evidence`, no citations, 2.27 seconds |
| Composer question submitted from the actual webpage | HTTP 200, supported answer, three expandable citations; no browser application errors or mobile horizontal overflow |

The first and repeat timings are observations, not a controlled cache-speed benchmark. Model warm-up and source/document cache state can both affect latency. A separate browser generation selected three citations instead of two; the factual answer remained correct, but not every citation is necessary. The Music excerpt explicitly names Hans Zimmer and supports the composer claim. These examples establish integration, not general answer accuracy or prompt-injection protection.

The compact record is `evals/movie-rag/smoke-2026-10-10.json`. Model digests, generation settings and a prompt hash were not pinned/captured for these smoke requests; this is not a reproducible holdout report.

## Next hands-on step: label real questions in the app

Before adding agent branches, try these in **Interstellar → Discuss** and inspect the expanded evidence:

1. “Who composed the music for Interstellar?” — expected factual answer: Hans Zimmer.
2. “Which instrument was chosen as the primary instrument for the score?” — expected: the Temple Church organ. Check the retrieved passage rather than assuming the model used it.
3. “What did I write in my private diary after watching Interstellar?” — expected: abstention without citations.

For each question, record the expected fact/status, whether at least one returned excerpt supports it, whether the answer includes it, and whether extra unsupported claims appear. Write the expectations before looking at the generated answer. Repeating a question can reveal variation, but those repeats are not independent evaluation cases.

This distinguishes two failures: **retrieval failure** means the supporting evidence was not selected; **generation failure** means it was available but the answer omitted or misused it. A cosine score alone cannot tell us whether an answer is supported. We will turn these labels into the first real-movie evaluation set; you keep ownership of the AI decisions, and the assistant builds the runner and checks.
