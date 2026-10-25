# 46 — Making quiz generation useful without weakening its checks

## The problem we investigated

The app already served saved quizzes. Generating more was less reliable: the model often proposed an unsupported answer or could not find a corroborating script scene. A passing verifier evaluation did not prove that retrieval and generation produced useful questions.

The fresh baseline accepted no Inception question and one Matrix question. The Matrix question substantially overlaps an existing topic. After the changes, the final local inspection accepted one new Inception question and no Matrix question. All inspections left the database unchanged. This is a narrow working improvement, not broad production readiness.

## How the button connects to the backend

The frontend’s quiz panel sends an explicit request with spoiler consent. `generate_more` loads the saved collection and acquires the shared AI slot. This prevents several expensive local-model workflows from running at once. It then calls `StoryRag.quiz` for movies qualified for expansion. The final accepted question is appended through the existing SQLite publisher. Later page loads read that saved result without calling the model again.

Main files:

- `frontend/src/components/movie-quiz-panel.tsx`: button, pending state, preserved choices and refreshed quiz.
- `backend/src/movie_companion/quiz_generation.py`: consent, availability, inference slot, question limit and atomic publication.
- `backend/src/movie_companion/story_rag.py`: evidence selection, bounded workflow and private traces.
- `backend/src/movie_companion/story_verification.py`: question writer, scene selector, blind option check and final reviewer.
- `backend/src/movie_companion/story_units.py`: complete plot sentences and exact source offsets.
- `backend/src/movie_companion/screenplay_retrieval.py`: persistent script vectors, narrative matching and hybrid scene retrieval.

There is no LangChain dependency in this workflow. These are ordinary asynchronous Python functions, typed records and HTTP calls to local Ollama. Learn what each stage does before introducing a framework.

## Step 1: choose unused, retrievable story evidence

The previous code selected whole plot groups. One paragraph might contain three separate events, while a retrieved script chunk described only one. We now split validated plot groups into complete sentences. Where a sentence starts with a pronoun, preceding context is retained when it fits the 600-character limit. Every unit keeps exact start/end offsets into its original article.

Embeddings estimate which units overlap least with existing questions. A second ranking estimates which units have related narrative passages in the script. Reciprocal rank fusion combines the two rankings: each candidate gets a contribution of `1 / (20 + rank)` from each list. Equal scores share a rank. Overlapping units cannot consume every context slot.

This combination is a candidate-selection heuristic. A high similarity or fused score does not establish that a claim is true. The later source checks decide that.

## Step 2: write a proposal from the released-film account

Ollama receives up to three W units and previous questions. It returns at most one seed containing:

```json
{
  "question": "How many years did Cobb and Mal experience in Limbo during their experiment?",
  "answer": "fifty years",
  "wiki_alias": "W1",
  "distractors": ["one night", "three days", "ten hours"]
}
```

This seed is not approved content and has no script citation. It lets us formulate an actual retrieval query before looking for screenplay support. If the answer is not copied literally from the released-film account, one bounded repair is allowed. Invalid outputs do not go straight into SQLite.

## Step 3: retrieve scenes for that precise question

The query includes the question and proposed answer. We search the registered movie/version only. Embedding ranking finds related dialogue; BM25 gives rare matching words more weight. Their ranks are combined before retrieving bounded candidates.

A small child chunk locates a scene. Code then expands its context by up to 300 characters on each side, retaining line boundaries and the scene boundary. The resulting excerpt cannot exceed 1,200 characters. Opening/title material is excluded. Source revision, movie identity and exact text offsets are rechecked.

The old Matrix script differs from the released film in important ways. A shared name or word does not make an old draft a source of truth for a scored question.

## Step 4: select a scene, then verify the answer

The selector receives the proposed relation and available S excerpts. It returns a required source ID or declines. Another scene, a later event or another character’s belief is not automatically a contradiction; an incompatible account of the same event is.

One early failure came from making the source ID optional. The model omitted it while claiming agreement. Another came from asking the model to reproduce script formatting. We now require the ID in the response schema and let code attach the exact original excerpt. The model cannot supply a new citation URL or invent the stored quote.

Code inserts the correct answer into the four options and determines its index. The model does not do option-index arithmetic.

Two checks follow:

1. **Blind option check:** sees the question, all four options and released-film evidence, without being told which option the writer selected. Exactly one option must be supported, with literal supporting evidence.
2. **Cross-source review:** checks the complete question/answer relation, script agreement, objective scoring and plausible distractors. Unsupported premises, conflicting events and multiple valid answers are withheld.

Sources are untrusted data. The model has no shell, filesystem, database or arbitrary network tools. Code owns publication, source IDs, quotes and permission checks. Prompt instructions help, but they are not the action-permission boundary.

## Step 5: recover within a fixed budget and preserve saved content

At most three different evidence batches are attempted, with an 80-second limit per attempt and no new attempt after 90 seconds of workflow time. At most two questions can be accepted. The API retains its overall 180-second deadline. Schema failures, insufficient evidence and rejected candidates cannot replace a saved collection.

Before saving, duplicate stems are checked against existing questions and new accepted stems. String similarity is only a partial novelty check: differently worded questions can still test the same detail. Previous-topic guidance and manual inspection remain useful; a broader labelled novelty evaluation is still needed.

SQLite publication uses the previous preparation timestamp as a compare-and-swap condition. If another update has changed the collection, the publisher rejects the stale write. Facts remain intact, and new citation revisions are added to the source manifest.

## What the evaluations mean

The inspector calls the real model and keeps proposed seeds, accepted questions, decisions, timing and implementation identity. It never publishes. It checks that saved content remains unchanged and counts internal attempt errors separately from top-level failures.

The final two-film inspection proposed six seeds: one accepted new Inception question, five withheld, zero attempt errors. Matrix did not demonstrate useful expansion and therefore does not receive that capability merely because verifier checks pass.

After activation and backend restart, a real API request generated and saved the Inception question in 90.90 seconds. The quiz grew from ten to eleven questions; the original questions and all facts stayed intact. A fresh API read and browser reload showed the persisted result. This separate publication check proves the inspected workflow connects to the app, while its observed latency motivates later background jobs.

Eight real-film development cases use source-version/offset references. The gate also reruns twenty consumed synthetic cases. Their expected labels are support/withholding decisions, not fixed model wording or embedding thresholds. The saved reports record false approvals, useful acceptance, errors and mismatches. Both data sets are development/regression evidence; they do not establish general accuracy on unseen movies.

The final gate matched 27 of 28 labels, with zero false approvals and zero errors. All negative cases were withheld. Three of four useful real-film cases were accepted; Yusuf's recruitment was withheld because the supplied script scene recommends him without establishing completed recruitment. We retained the original positive label and this mismatch. The gate passes its preregistered 75% useful-acceptance threshold; passing does not mean every useful case succeeds.

Read `evals/movie-rag/story-quality/README.md` and `gate-v9.json` for the measured outcomes. The runtime checks selected generation/retrieval module hashes against the evaluated and loaded code, along with the model digest. Editing those modules closes the gate until evaluation and restart. Expansion additionally requires a matching successful generation inspection for that movie.

## Questions and answers

**Why did adding more agents not automatically fix generation?** Each stage still needs useful evidence. Repeated writing/review calls over the wrong scene cannot recover an event absent from that excerpt.

**Why use both lexical and vector retrieval?** Dialogue can use different wording from a plot summary, which favors embeddings. Exact names, objects and phrases can be missed by embeddings, which favors lexical matching. Neither proves support.

**Why does the model choose IDs instead of copying citations?** IDs select already-validated records. Code retrieves their original bytes and source URLs. This avoids invented links, escaping errors and changed quotes.

**Why can an evaluation pass while a movie cannot generate more questions?** A verifier can correctly accept/reject supplied examples while the writer/retriever fails to produce a good new candidate. We now measure and gate those capabilities separately.

**Are these parallel autonomous agents?** These are explicit writer, selector and reviewer stages with bounded orchestration. Local model calls remain serial under the shared inference slot. Justified parallel source fetching, persistent jobs and comparative agent evaluations are later milestones.
