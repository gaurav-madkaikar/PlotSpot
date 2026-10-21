# 48. Automatic search and broader saved content

Typing searches after a 350 ms pause. Knives Out and The Truman Show each now have five filmmaking facts and ten scored story questions, saved once in SQLite. Complete facts/quiz collections cover six films. The metadata catalog is much larger; having a poster and synopsis does not mean a film has a reviewed quiz.

## Follow one search through the code

Start in `frontend/src/components/movie-search.tsx`:

1. `draft` is the text in the input; `query` is the committed `q` in the URL. Changing `draft` makes typing immediately responsive.
2. An effect starts a 350 ms timer. Another keystroke runs its cleanup, cancelling that timer and starting a fresh one.
3. After a pause, `update('q', value, true)` changes the URL. `true` replaces the current history entry, avoiding an entry for every typing pause. Filter/page navigation retains its existing history behavior.
4. A new query removes old pagination and external person-lookup state, preserving genre, language and runtime.
5. The URL builds a React Query key containing all request parameters. A different key requests matching results through `searchMovies` in `frontend/src/lib/api.ts`.
6. The API client passes React Query's `AbortSignal` to `fetch`. A query losing its observer can cancel its request; each response also belongs to its own key, so an old query cannot replace the newest result list.
7. Successful responses are reusable for five minutes. This is the existing frontend result cache, distinct from SQLite metadata and saved facts/quizzes.

Enter or the magnifier still submits immediately; they are optional shortcuts. Filters apply immediately. Emptying the input returns to the filtered collection. Composed text input waits for `compositionend` before starting its timer.

Trim whitespace for the request, but preserve unfinished input. If someone types `Knives `, pauses, then types `Out`, removing the trailing space would accidentally search `KnivesOut`. Synchronization preserves a draft whose trimmed value already matches the URL.

`useCallback` retains the update function between renders when its dependency is unchanged. The effect can list that function as a dependency without treating an unrelated render as a new function. This controls when effects rerun; it does not make requests synchronous.

The redundant invitation sentence and large panel were removed. Optional live TMDB lookup remains a small “More title and person matches” action. Ordinary automatic search uses the local keyword endpoint.

## From source to a visible movie collection

Preparation runs independently of viewer requests:

`registered Wikipedia source → versioned private snapshot → authored bank → evidence compilation → validated SQLite publication → feature inventory → facts/quiz GET → UI`

- `wikipedia_source.py` fixes the movie/article mapping and validates title, revision and section boundaries.
- New banks: `content_banks/546554.json` and `content_banks/37165.json`. These are assistant-authored and source-reviewed starter collections, rather than Ollama outputs.
- `reviewed_content.py` admits those IDs, locates supporting markers only in the appropriate evidence branch, and selects bounded complete-sentence citations with stable passage IDs.
- `scripts/prepare_movie_content.py` compiles before publication. Missing evidence or wrong sources fail before storage. Existing collections are retained unless explicitly refreshed.
- `content_store.py` requires five unique facts, ten scored questions, distinct options, explanations and valid citation manifests. Writes are atomic; concurrent replacement uses the existing timestamp condition.
- `main.py` reads readiness from the saved collection. The frontend shows those sections and loads content after spoiler consent. Viewing, replaying and reopening require no model call.

| Film | Fixed Wikipedia revision | Facts | Scored questions |
|---|---|---:|---:|
| Knives Out | [1378593030](https://en.wikipedia.org/w/index.php?oldid=1378593030) | 5 | 10 |
| The Truman Show | [1378575188](https://en.wikipedia.org/w/index.php?oldid=1378575188) | 5 | 10 |

Every item and answer was inspected against its citation and surrounding context. Questions cover story events and endings; facts cover production, design, props and music. Complete-content hashes confirmed that the original four saved collections remained identical.

Reports are in `evals/movie-rag/coverage/`; full source text remains in ignored private snapshots. Live verification records source/bank hashes, feature inventory, spoiler protection and equal repeat reads.

## Questions and answers

**Is debounce an AI feature?** No. It is frontend scheduling. Keyword search requires neither Ollama nor embeddings. RAG remains in separate discussion and evidence-generation workflows.

**Does abort guarantee the backend stops?** No. It cancels the browser's wait/transfer where supported; the server might already be processing. Debounce reduces requests before they start.

**Why not generate every time someone opens a movie?** Preparation provides consistent, fast reads and review before users see content. Generation remains an explicit preparation or qualified expansion operation.

**Do citation markers prove an answer correct?** No. They prove that the expected section contains required wording. Review must check the actual claim, context, ambiguity and distractors. Automated fixtures are regression checks, not an independent accuracy benchmark.

**Can the new films Generate more?** Not yet. They have complete saved starter quizzes and registered discussion sources. Script-assisted expansion has a separate per-movie gate; adding a bank does not bypass it.

**Is coverage universal?** No. Six films have full saved collections; other films retain metadata and truthful unavailable-content states. Further coverage should repeat source inspection, preparation and quality verification.

## Verification

738 backend checks passed, including the new banks, missing-evidence and wrong-film failures, and generation-free reads. Browser checks cover typing coalescing, page reset, filters, clearing, stale responses, immediate Enter, composed input, whitespace preservation and saved facts/quiz journeys. The production build passes. Live search returned Knives Out without a submit click, and its saved facts and ten-question screen were inspected.
