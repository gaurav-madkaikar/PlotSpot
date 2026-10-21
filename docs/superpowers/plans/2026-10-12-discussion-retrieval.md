# Discussion retrieval and useful citations

**Goal:** Repair missed concrete story evidence while retaining filmmaking/theme discussion, abstention and movie/spoiler isolation.

**Architecture:** Add a small discussion retriever that validates eligibility with the existing boundary, recognizes explicit event cues conservatively, and fuses BM25 word ranks with vector ranks. Story-event cues restrict classified evidence to Plot; interpretation, production, mixed and ambiguous questions keep the full eligible article. Preserve unclassified learning fixtures. Reserve the strongest lexical candidate in the three-passage budget so rare matching actions cannot disappear behind generic commentary. Generation remains one local chat call. The model selects bounded, code-owned verbatim excerpts through a schema enum; code checks membership and source presence, folds repeated valid excerpts and maps them to canonical citation IDs. Public API response shape is unchanged. Literal presence does not establish semantic support.

**Trade-offs:** Raising top-k alone increases prompt size without fixing relevance. An LLM classifier/reranker adds calls, latency and another failure mode. Deterministic routing/rank fusion is inspectable and inexpensive but imperfect; it is not entailment or a confidence score. No film-name/ID rules, semantic movie discovery, new sources, automatic bank publication or weakened story gates.

**Files/interfaces:** `discussion_retrieval.py` owns `retrieve_discussion_passages(question, query_vector, passages, query_model, movie_id, allow_spoilers, k=3)` and optional bounded ranking trace. `movie_qa_learning.answer_movie_question` calls it after query embedding and keeps its public return/callback contract. `grounding_learning` owns excerpt options, structured generation and citation binding; an optional support trace joins the ranking trace for developer evaluations. The registered-movie inspection records retriever/prompt identities and supports an explicit archived vector-only baseline. Existing labels/reports are immutable; additional source-reviewed cases are frozen before model outputs and reported as development checks.

- [x] Add regression checks for an action obscured by themes, interpretation/mixed/production routing, missing plot evidence, lexical fallback, invalid vectors, permission/model/movie scope and deterministic non-mutating ranking.
- [x] Implement the retriever and wire the shared discussion function; keep one embedding and one chat request. Strengthen citation binding with bounded excerpt selection while preserving the public response schema.
- [x] Preserve the earlier five-case inputs/report. Freeze additional questions across Dark Knight and other registered films before running models. Compare baseline/candidate under the same source/chunks/models and report passage IDs, actual answers, failures and latency; manually inspect citations.
- [x] Run regression/API/browser checks and build, restart the owned backend, verify the formerly missed event live, preserve saved banks and document learning/checklist/progress.

**Result:** 970 backend checks and sixteen browser journeys pass. Seventeen-case
development comparison: 15 candidate passes versus 11 baseline; annotated support
hit at three: 14/14 versus 11/14. All three labelled abstentions pass in both arms;
six separate fixed-evidence grounding checks pass. The formerly missed Dent event
and Arrival's future visions work through the live API; Dent's source is visible
in the existing UI. Original spoiler preference restored. All eleven banks and
the independent script gate remain unchanged. See lesson 58 and
`evals/movie-rag/coverage/discussion-retrieval-review.json` for the unresolved
clipped makeup citation, phrase-check limitation, unnecessary excerpts and higher
observed generation duration. No production-quality or publication qualification
is claimed.

Execution follows the user's approved continuation inline. No commits or delegated workers are required.
