# Lesson 12 — turn a source into overlapping passages

## Why chunking comes before storage

So far, your evidence was already split into small passages. Real production articles and interviews are longer. Chunking divides a source into manageable pieces, so retrieval can find the relevant portion and generation can receive bounded evidence.

```text
Source text + source metadata
           ↓
Your chunks: text + original start/end offsets
           ↓
Later: passage IDs + movie/source/revision/spoiler metadata
           ↓
Embeddings → persistent evidence index → retrieval → grounded answer
```

This slice is pure Python: no model, HTTP request, LangChain, or vector database. The assistant will supply persistent storage after reviewing your chunking loop. We are not ingesting real articles or adding app routes yet.

## The initial baseline

We use **characters** for this teaching exercise: a maximum window length and a fixed character overlap. The product design's 450-token chunks and 80-token overlap are a later token-aware strategy; these units are not interchangeable. Character windows can split words or sentences. They are easy to inspect but are not our final article chunking policy.

Overlap repeats a small tail of the previous window at the beginning of the next. It can preserve context across a boundary, but increases storage, embedding work, and duplicate retrieval. Zero overlap is valid. Overlap must be smaller than the chunk size so the window advances.

## Worked example

For text `ABCDEFGHIJK`, `max_chars=5`, and `overlap_chars=2`:

| Chunk | Start | End (exclusive) | Text |
|---|---:|---:|---|
| 1 | 0 | 5 | ABCDE |
| 2 | 3 | 8 | DEFGH |
| 3 | 6 | 11 | GHIJK |

The second chunk repeats `DE`; the third repeats `GH`. Once a chunk reaches the source end, stop. Do not generate an extra chunk containing only the already-covered tail.

Python slicing uses an exclusive end: `text[0:5]` includes positions 0 through 4. These are Python string positions, not UTF-8 byte offsets or tokenizer positions. A grapheme made of multiple Unicode code points can be split by this simple baseline.

## Your coding slice

Implement only `split_windows` in `backend/src/movie_companion/chunking_learning.py`.

The wrapper supplies valid nonblank text, `max_chars`, and `overlap_chars`. Return a list of `TextChunk` records, each containing `start`, `end`, and the exact original `text[start:end]`.

Your loop should:

1. Begin at source position zero.
2. Calculate the next end, capped at the source length.
3. Append a `TextChunk` for that span.
4. Stop when the end reaches the source length.
5. Otherwise, advance the start to the previous end minus overlap.

Do not call `.strip()` on chunk text: that would disconnect the text from the original offsets. Do not generate vectors or source IDs yet. The assistant-owned wrapper rejects invalid inputs and checks full coverage, source slices, window sizes, and overlap consistency.

## Useful Python patterns

Cap a value:

```python
limited = min(12, 10)  # 10
```

Track progress and stop a loop:

```python
position = 0
while position < 10:
    print(position)
    if position >= 6:
        break
    position += 3
```

Construct a record:

```python
piece = TextChunk(start=0, end=3, text="abc")
```

These are separate patterns, not the complete solution. Your stopping condition matters: reaching the source end must be checked before advancing into another overlapping window.

## Run your checks

From `backend`:

```sh
.venv/bin/pytest tests/test_chunking_learning.py -q
```

At preparation, five windowing tests intentionally fail against the learner stub and 14 assistant boundary tests pass. All 136 previous backend tests pass independently. The full suite includes the unfinished exercise, so it is intentionally red until you complete it. No UI behavior is affected.

After implementation:

```sh
.venv/bin/python scripts/try_chunking.py
```

The script prints overlapping spans of a clearly fictional production article. No Ollama service is needed. Inspect shared text at boundaries, source offsets, and the final chunk. Later you will feed chunk texts into your embedding helper while the assistant adds persistence and provenance.

## Why source offsets matter

A chunk must retain its relationship to a source revision. Start/end offsets let us show where evidence came from and verify the stored text against that revision. Offsets alone are not provenance: the next storage record will also need source identity, revision, movie identity, spoiler classification, and embedding version. If source text changes, old offsets may no longer refer to the same content.

Chunking cannot fix unsupported sources, prompt injection, or spoiler labels. It can also damage context by splitting a qualification from its claim. We will compare chunking choices using labelled retrieval cases rather than assume a larger overlap improves quality.

## Concepts to explain afterwards

1. Why stop immediately when a window reaches the source end?
2. Why require overlap smaller than the window size?
3. Why preserve whitespace and original offsets?
4. How are character counts different from token counts?
5. What are the costs and benefits of overlap?

We will record answers after reviewing your implementation. Persistent evidence storage follows this slice; it has not been added yet.

## First learner review — 2026-10-10

The learner used a `for` loop with step `max_chars - overlap_chars`, which correctly advances windows with the requested overlap. Five windowing tests fail and all 14 boundary tests pass. The function was left unchanged for a focused correction.

Two issues need fixing: `TextChunk.end` must be exclusive, matching `text[start:end]`, so cap the end at `len(text)` rather than `len(text) - 1` and remove the extra `+ 1` in the slice. Then stop immediately after appending a chunk whose end equals the source length. A range over all start positions otherwise generates an unnecessary overlap-only tail.

For `ABCDEFGHIJK`, width 5 and overlap 2, starts are 0, 3, 6, 9. The chunk beginning at 6 already reaches end 11; stop there, rather than emit another chunk at 9. No valid demonstration output is claimed before this correction.

## Completed review — 2026-10-10

The learner corrected exclusive end positions and added the break immediately after the final append. All 19 chunking cases and all 155 backend cases pass. The assistant left the implementation unchanged.

The fictional article demonstration returned four spans: `[0:100]`, `[80:180]`, `[160:260]`, and `[240:313]`. Adjacent chunks overlap by 20 characters; the last is shorter, reaches the 313-character source end, and has no redundant trailing chunk. Words split across boundaries, as expected for this character-window baseline. No model calls, persistence, or app integration were involved.

## Answers to the review questions

1. **Why stop at the source end?** The current chunk already covers the final characters. Continuing the range can create another chunk containing only an already-covered overlap tail, increasing duplicates without adding information.
2. **Why overlap smaller than the window?** The step is `max_chars - overlap_chars`. It must be positive so each window advances. Equal or larger overlap would prevent useful progress.
3. **Why preserve whitespace and offsets?** Each record must match the original source slice exactly. Trimming changes that correspondence and can make source highlighting or revision verification incorrect. Blank-source handling belongs to the wrapper.
4. **Characters versus tokens?** Python string slicing uses Unicode code-point positions. Tokens are model-specific pieces of text; one word can have multiple tokens, and punctuation or whitespace also contributes. Character size does not guarantee a token budget. This baseline can also split words and multi-code-point graphemes.
5. **Overlap tradeoffs?** It preserves some context across boundaries, but repeats content, increasing embedding/storage work and potentially returning near-duplicate evidence. It cannot guarantee that every sentence or qualifying detail survives intact. Choose it using retrieval evaluations, not intuition alone.

Next: persist attributed chunk records and their embeddings, with source revisions and model/version consistency, so document embeddings can be reused across runs.
