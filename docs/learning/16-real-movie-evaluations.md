# Evaluate the actual movie RAG pipeline

You have built an end-to-end RAG feature. Now we need evidence about how it behaves. This task is part of the main project: the runner calls your actual `answer_movie_question`, not a substitute pipeline. You will write one human-labelled movie question; the assistant has supplied the runner and boundary checks.

## The important distinction

Suppose the question is “Who composed the music for Interstellar?”

- **Retrieval check:** did the top three passages include the source statement naming Hans Zimmer?
- **Answer check:** did the reply answer Hans Zimmer and cite a supporting passage?
- **Human support check:** do all factual claims in the reply follow from the cited text?

An answer can name the correct composer from the model's memory while citing unrelated evidence. That should fail the labelled support checks. Conversely, the right passage can be retrieved while the model unnecessarily abstains. That is a generation failure with successful retrieval.

We check expected facts and behavior, not identical full sentences. “Hans Zimmer composed it” and “The composer was Hans Zimmer” can both pass a phrase check. A phrase appearing in “It was not Hans Zimmer” could also pass that simple check incorrectly. That is why human claim-support review remains necessary.

## What the assistant supplied

| File | Purpose |
|---|---|
| `backend/scripts/evaluate_movie_rag.py` | Freeze public evidence once, then run local inference evaluations |
| `backend/src/movie_companion/movie_rag_eval.py` | Validate labels and calculate checks separately |
| `evals/movie-rag/cases.json` | Two worked development labels; your next case goes here |
| `data/private/movie-rag/source.json` | Ignored local full source and attribution |
| `data/private/movie-rag/passages.json` | Ignored local catalogue of every chunk's ID, text and character span |
| `evals/movie-rag/baseline.json` | Real-model observations; created by running the command below |

The source was prepared from Wikipedia revision `1379200125`, with **186** 600-character chunks and 100-character overlaps. Its snapshot fingerprint includes source content/revision, embedding model tag and chunk settings. A changed source or unknown labelled passage ID stops evaluation before model inference. Evaluation uses a separate Chroma store under `data/chroma/eval`; no internet fetch happens during the inference run. Whole-article evidence may contain spoilers.

Your pipeline now has an optional `on_retrieved` argument. The runner passes `hits.extend`, which records the retrieved hits before generation. Normal app calls omit it. This callback observes the selected evidence; it does not choose passages or change your algorithm. Copying the list keeps the observer from altering the pipeline's hit list.

## A worked label

The composer case in `cases.json` has these important fields:

```json
{
  "id": "composer",
  "question": "Who composed the music for Interstellar?",
  "expected_status": "answered",
  "relevant_passage_ids": ["e75a7bb9fce05a8541de5c8596eb11b7_042"],
  "required_phrase_groups": [["Hans Zimmer"]]
}
```

The expected passage ID comes from reading the Music statement in the frozen catalogue, not copying a model's chosen citation. The ID changes if the source/chunk configuration changes. Labels intentionally cover reviewed supporting passages, not every possible supporting mention throughout Wikipedia.

Each inner phrase list contains acceptable alternatives: `[["organ", "pipe organ"]]` means either phrase satisfies that group. Two groups such as `[["organ"], ["Temple Church"]]` require a match in both groups. These are substring smoke checks, not semantic entailment.

The personal-diary question expects `insufficient_evidence`, with empty supporting IDs and phrase groups. The public movie article cannot support a user's private diary contents. This case is excluded from retrieval hit/recall denominators, rather than counted as a retrieval failure or free success.

## Your hands-on slice

Add a third object to the `cases` list in `evals/movie-rag/cases.json`:

1. Give it ID `primary-instrument` and question **“Which instrument was chosen as the primary instrument for the score?”**
2. Search the frozen `passages.json` for `primary instrument`. Read the complete matching passage; neighbouring overlapping chunks may end mid-sentence.
3. Set `expected_status` to `answered`. Copy the ID of a passage that actually supports the expected fact into `relevant_passage_ids`.
4. Set `required_phrase_groups` to `[["organ"]]`. The required fact is the instrument; the question does not require its location. If you change the question to ask for location too, label that additional fact explicitly.
5. Keep the dataset's `source_snapshot` unchanged and change `version` to `movie-rag-dev-v2` because the labelled set changed.

Write this label before inspecting the generated response. Do not tune labels merely to make a failing response pass. This is human supervision for your AI feature, not another helper implementation exercise. After this review we can use the measured baseline to expand features and agent decisions.

## Run it

From `backend`:

```sh
.venv/bin/python scripts/evaluate_movie_rag.py --output ../evals/movie-rag/with-instrument.json
```

Ollama needs to be running with the already used `nomic-embed-text:v1.5` and `llama3.2:3b` models. The runner does not download models. Initial evaluation-store ingestion embeds document chunks; unchanged later runs reuse them. Each question still gets a query embedding and generation. Keep baseline reports when adding labels or changing prompts so comparisons remain reviewable.

`--prepare-source` has already been run. Do not run it again: it refuses to overwrite existing source/labels. On another machine, run that command first to create local inputs, then review labels for its source revision; preparation will also refuse if tracked labels already exist. Transferring the reviewed frozen local inputs preserves this labelled snapshot. Source preparation is not currently an automatic cross-machine dataset-recovery tool.

The process exits 0 if all automated checks pass, 1 if cases fail, and 2 if setup is invalid/unavailable. A failed case is useful evidence; inspect the report instead of assuming the program crashed.

## Read the report

`supporting_hit_at_3` asks whether at least one labelled supporting ID was retrieved. `annotated_id_recall_at_3` is the fraction of your annotated supporting IDs retrieved; it does not measure every relevant passage in the article. Case failures also show wrong status, missing required phrases, foreign citation IDs or absence of a labelled supporting citation. If generation fails, retrieved hits are retained for diagnosis.

The report includes cosine scores, exact selected IDs, answer, expected status, source/dataset/prompt/pipeline hashes, available installed model digests and elapsed time. It omits full article text. Model sampling remains at defaults and token counts are unavailable through the current helper. Document cache identity still uses a model tag rather than its digest; swapping the weights under a tag requires a fresh evaluation store.

These are development cases, not a held-out benchmark. A two- or three-case pass does not justify a broad accuracy or prompt-injection claim. Existing `evaluate_grounding.py` still tests generation with fixed fictional evidence, including injected source instructions; this new runner adds real embeddings and retrieval.

## First observed run — 2026-10-10

The two starter cases passed their automated checks, with zero generation errors. The composer question retrieved the reviewed Music passage first (cosine 0.8090), answered Hans Zimmer, and cited that passage plus a nearby chunk. The missing-personal-evidence question abstained without citations even though its top passage had cosine **0.7131**. A fairly high similarity score therefore does not establish that the question is answerable: semantic similarity is not evidence support.

Initial evaluation-store ingestion reported `indexed`; the report captures installed model digests, source fingerprint and dataset/prompt/pipeline hashes. Inference durations were 5.386 and 2.101 seconds, excluding source preparation and document ingestion. Only one case has labelled supporting evidence, so the hit count is **1/1 labelled case**, not a useful broad “100% retrieval accuracy” claim. Full claim-support review remains pending; the composer fact itself is supported by the reviewed Music statement.


## Learner label reviewed — 2026-10-10

Your `primary-instrument` question uses the correct supporting chunk `_043`, expected status `answered`, and required phrase `organ`. You also correctly bumped the dataset version to v2 and kept its snapshot binding. The only input mistake was copying the earlier case's `missing-personal-evidence` ID. The assistant renamed it to `primary-instrument`; IDs uniquely identify report rows and regression cases.

All 217 backend tests pass. The new three-case real run is retained as `evals/movie-rag/with-instrument.json`: two automated passes, one generation/validation failure, and supporting retrieval hits for both labelled answerable cases (2/2). The instrument's correct chunk ranked first at cosine 0.7029. It is therefore not a retrieval miss or a wrong label. The initial failure was a ValueError; its raw output was not captured, so the exact failed constraint cannot be established retrospectively.

Two diagnostic repeats are retained in `evals/movie-rag/instrument-diagnostic.json`. The first returned valid JSON but unnecessarily abstained; the second returned a valid supported answer identifying the Temple Church organ. The prompt, labels and model settings were not changed for these repeats. Do not replace the original report with the passing repeat or weaken the label to accept abstention. This is observable generation variability; the current helper uses unpinned model defaults. The runner now records a bounded error message as well as error type to improve diagnosis of future failures.

The next reliability milestone is stronger output-contract enforcement and controlled generation settings, followed by repeating the same cases without changing their expectations. Structured output can address JSON/schema failures; it cannot by itself fix unnecessary abstention or prove factual support.
