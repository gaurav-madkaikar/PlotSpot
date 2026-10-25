# 40. Connecting retrieval to facts and quiz generation

The draft preparation command now uses RAG by default. It retrieves evidence before asking the local model to propose facts and questions. Published app content still comes from the reviewed SQLite collections; this increment does not automatically replace them.

## The flow in plain words

1. Load a saved, validated Wikipedia article snapshot for one movie.
2. Split its sections into overlapping windows and ask Ollama for document embeddings.
3. Save those vectors and their source identity in Chroma. Reuse them when the same snapshot is requested again.
4. Embed a bounded set of topic queries, such as character decisions, ending events, filming methods and music recording.
5. Rank story windows for quiz topics and background windows for fact topics.
6. Reconstruct complete sentence groups from the ranked windows, preserving original text and offsets. Do not select the same group twice.
7. Send at most two story and two background passages per batch to the existing generator, then the critic.
8. Save drafts and the retrieval trace for review. Insufficient or rejected material leaves the result incomplete.

No LangChain is required. These are ordinary Python functions, async HTTP requests, Pydantic records and a persistent vector store.

## Where the code connects

- `content_evidence_retrieval.retrieve_draft_evidence` coordinates indexing, query embeddings, filtering, ranking and selection.
- `ingestion_learning.ingest_source` checks whether the exact snapshot is already saved. A cache hit skips document embedding.
- `EvidenceStore.load_snapshot` verifies that the saved windows, metadata and vectors match the requested snapshot before returning them.
- `proposal_evidence.evidence_pools` creates complete sentence groups and provenance. It excludes article-navigation text and Cast listings that mix character descriptions with plot details. Casting-process sections remain eligible.
- `content_preparation.prepare_drafts` accepts an async evidence loader inside its overall deadline. It saves the retrieval trace before calling the generator.
- `prepare_content_drafts.py` wires the real Chroma store and local embedding model into that loader.

The direct coordinator API retains its section-selection default for compatibility. The command uses `--evidence-mode rag` by default; `--evidence-mode sections` explicitly selects the old comparison baseline.

## Why we embed windows but generate from complete sentences

A window might start halfway through a sentence. Such a fragment can omit who performed an action or what a pronoun refers to. Ranking works on the saved section windows, but generation receives complete groups of sentences of at most 600 characters.

Each complete group receives the highest cosine score among windows covering at least half of that group. We select unused groups in descending score order, preferring different sections for the two background slots. This is a simple context-reconstruction heuristic, not an entailment model. A complete sentence can still contain an unresolved pronoun; the critic must abstain when context is insufficient.

## The queries are bounded and application-owned

Eight story topics and eight background topics are defined in `TOPICS`. A full run embeds those sixteen queries in one request. They cannot request arbitrary tools, change the movie identity or grant publication permission.

Query vectors use `search_query: ` and source windows use `search_document: `. Both use `nomic-embed-text:v1.5`; the command verifies its reviewed digest against the installed Ollama artifact.

Retrieval is scoped to one exact movie/source snapshot. Purpose filtering happens before ranking. Plot sections cannot compete for fact slots. Unknown sections are excluded. The context itself remains untrusted data in the generator and critic prompts.

## What is cached

`data/content-evidence/` contains the persistent Chroma evidence index and is excluded from Git. Its fingerprint includes source text, revision, sections, movie identity, embedding model, prefixes and window settings. Different snapshots retain separate identities.

The saved document vectors survive a backend restart. Topic query embeddings are recomputed on each preparation run; they are not currently cached. Draft JSON reports are separate checkpoints. Reviewed SQLite collections are a third, independent storage layer that serves the UI without generation calls.

## Inspect retrieval without generating anything

From the backend directory:

```bash
.venv/bin/python scripts/inspect_content_retrieval.py \
  --source-snapshot ../.cache/source-snapshots/27205.json \
  --output ../evals/movie-rag/my-retrieval-inspection.json
```

The report contains topics, purpose filters, top window IDs and scores, selected source spans, exact evidence text, snapshot cache state, model artifact and elapsed time. It grants no publication permission.

To run one complete retrieval/generation/review batch:

```bash
.venv/bin/python scripts/prepare_content_drafts.py \
  --source-snapshot ../.cache/source-snapshots/27205.json \
  --report ../evals/movie-rag/my-one-batch-drafts.json \
  --max-batches 1 \
  --deadline-seconds 120
```

At most eight batches are allowed, with a total deadline of at most 600 seconds. Indexing and retrieval are included in that preparation deadline. Local-model artifact checks have a separate bounded startup check. The optional structured critic remains available through `--verifier structured`; its previous evaluation did not establish a general quality advantage.

## What this step does not prove

A cosine score is a relative retrieval score, not a probability that a fact or answer is correct. We currently rank candidates without a calibrated relevance threshold. Fixed topics and novelty filtering can select weaker material when the best passages have already been used. Semantic duplicate questions can still occur even with different evidence passages.

Unit tests verify isolation, provenance, ranking with controlled vectors, cache reuse, budgets and failure behavior. They do not measure real movie-question quality. The real local runs are integration smoke tests, not a representative retrieval benchmark. A future labelled dataset should identify relevant source spans per topic, measure retrieval hit/coverage, and compare section selection against this retriever using the same generator and evaluation labels.

Script ingestion is not implemented here. It needs explicit source identity, scene-aware parsing and draft-versus-released-film compatibility. The existing early Interstellar script must not become sole evidence for a scored answer about the released film. External reporting for facts also needs separate source adapters.

## Questions and answers

**Is this RAG even though users are not asking a question?** Yes. The topic queries retrieve evidence that conditions the generator's output. Retrieval can support a background content-preparation job, not just a chat response.

**Are we embedding all 1,500 catalog movies again?** No. Catalog embeddings support discovery. This index contains the detailed source passages for the movie being prepared. We can ingest one movie when needed.

**Why not let the model search any website itself?** The current step needs inspectable, bounded retrieval with known provenance. Source acquisition is a separate capability; adding it later should not give the generator unrestricted network or publication access.

**Does a critic accepting a draft make it safe to publish?** No. Previous labelled evaluations demonstrated semantic failures. Accepted proposals remain reviewable drafts, and the reviewed app collections are kept intact.

**Does selecting an ending topic expose spoilers to everyone?** No. Internal draft preparation may read spoiler evidence; it does not serve those drafts. Existing app spoiler gates still apply to published quiz/discussion content. Section labels are not a reliable automatic spoiler classifier.

## Actual local results

On the saved Inception snapshot, the initial retrieval smoke test indexed the document windows and prepared eight batches / sixteen topic queries in **3.8 seconds**. A second run reused the saved snapshot in **0.47 seconds**. Trace inspection exposed a `Main article:` navigation line and Cast paragraphs containing character/plot descriptions; these were removed from candidate evidence. The final v2 retrieval run reused the same document index in **0.43 seconds**, with those inputs excluded. These single-run timings are not a hardware-normalized performance benchmark.

The original-policy one-batch RAG/generation/critic run took **61.29 seconds**, retaining **two fact drafts and zero questions**. The model produced two questions about production details, referencing background passages. Deterministic purpose checks rejected both before semantic review. The two facts described the Paris folding sequence's green screen/CGI work and the camera formats Nolan and Pfister tested but did not use. They remain drafts, not app publications.

The final retrieval policy selects exactly the same first batch as that integration run, verified by comparing complete evidence records. Later batches changed after the navigation/Cast fix. We did not rerun generation and relabel the original artifact as a final-policy run.

Reports:

- `evals/movie-rag/content-retrieval-inception-indexed.json`: original v1 cold-index smoke trace.
- `evals/movie-rag/content-retrieval-inception-cached.json`: original v1 cache-reuse trace.
- `evals/movie-rag/content-retrieval-inception-v2-cached.json`: final v2 filtered retrieval trace.
- `evals/movie-rag/preparation-inception-rag-one-batch.json`: one original v1 generation/review batch, with rejected quiz proposals preserved.

**574 backend tests passed.** The frontend was unchanged. The next generation improvement is separate fact and quiz inputs/calls so each branch receives only the right kind of evidence; malformed or unsuitable output must still be rejected rather than silently converted into a different question. Visible preparation progress and draft review remain subsequent app integration work.
