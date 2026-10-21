# 50. Evaluating facts on real movie evidence

This stage measures the existing local fact writer and verifier. It does not add another framework or silently publish generated content.

## Two different questions

A labelled challenge asks: **Can the verifier distinguish a supported fact from a plausible mistake?** We wrote expectations before running Ollama, using short production excerpts from six movie articles. Each film has one supported claim, one contradicted claim and one invented causal explanation. That gives six useful cases and twelve flawed cases.

A generation inspection asks: **What does the current writer actually produce from these excerpts?** Its proposals have no labels beforehand. We record the output, run the verifier and independent checks, then inspect the generated claims against their quotes. Passing the labelled challenge does not prove that every generated proposal is correct.

The models never receive the challenge labels. The writer receives only movie context and exact source sentences; it cannot see the intentionally flawed challenge proposals.

## How the pieces connect

1. `load_dataset()` verifies a snapshot's SHA-256 hash, registered movie/article/revision, section category, and exact text offsets. If anything differs, inference does not start.
2. `evaluate_quality()` sends the challenge proposals to the existing critic. It records the expected decision, actual decision, reason and time for each case.
3. `inspect_generation()` calls the existing `propose_article_facts()`. The model selects sentence IDs; Python attaches the original quote bytes.
4. The generated proposals go through the critic and separate quote, length, copied-prose and duplicate checks. An approved draft is still not permission to publish.
5. The runner writes durable report checkpoints. It has no content-store import or publication operation. A later run needs a new report path to preserve the earlier results.

These are evaluation tools, so they don't connect to a new consumer button. The app continues reading its saved movie collections.

## Why similarity is not enough

Suppose the evidence says a costume designer researched **1930s uniforms**. A claim saying **1990s uniforms** will share nearly all its words and may have high embedding similarity. It is still wrong. Likewise, evidence that two things happened does not establish that one caused the other.

Exact span checks establish that the quote exists. The critic checks whether the claim follows from it. A person should inspect hard cases and annotate independent examples. None of these checks alone measures source reliability or establishes that a Wikipedia assertion is true in the real world.

## Reading the metrics

- **Label matches:** actual decision equals the authored expectation. Rejecting every proposal cannot score perfectly because six should be accepted.
- **Useful acceptance:** how many of the six supported facts were accepted.
- **False acceptance:** how many of the twelve flawed claims were accepted. Lower is better.
- **Uncertain:** cases the verifier withheld because it could not establish support. Uncertainty is separate from rejection and does not automatically count as a correct label.
- **Errors:** missing, malformed or failed judgements. These stay in the denominator. A deadline also records all unfinished cases and movies.

The generation report has observation counts rather than an accuracy percentage. Its `eligible_drafts` count means the checks passed; it is not a human-labelled correctness score. This inspection uses isolated new topics and checks duplicate wording within each generated batch. The actual publication workflow additionally checks saved topics, reviewed publisher mappings and concurrent writes.

## Scope and limits

The six films are Parasite, Spirited Away, The Grand Budapest Hotel, Dune (2021), Knives Out and The Truman Show. The excerpts concern editing, English dubbing, costume research, desert lighting, character names and acting preparation. They avoid the evidence markers used in their published starter facts. Wikipedia contributors are attributed through revision URLs in the dataset and source manifest.

The labels are assistant-authored development expectations, not independent annotations. This is a fresh challenge before its first inference, and becomes consumed development evidence afterwards. The short excerpts and six films do not measure full RAG retrieval, source freshness, independent publisher corroboration, prompt injection, missing antecedents or catalog-wide reliability. The writer and critic use the same local model, so shared mistakes remain possible.

No embeddings are generated here: source passages are deliberately fixed to isolate writer/verifier behavior. The existing background RAG retrieves from Chroma in its separate workflow. Retrieval quality needs a separate labelled evaluation.

## Actual local run

Model: `qwen3.5:9b`, verified against the reviewed local digest. Temperature 0, seed 7, thinking disabled; the current writer allows 1,200 output tokens and critic 1,800. The baseline report pins the dataset, source snapshots, critic implementation and background workflow. These are single local-run timings, not latency targets or throughput measurements.

| Measure | Result |
|---|---:|
| Label matches | 18 / 18 |
| Useful facts accepted | 6 / 6 |
| Flawed claims accepted | 0 / 12 |
| Labelled errors or uncertain decisions | 0 / 18 |
| Challenge duration | 102.28 seconds |
| Generation inspections completed | 6 / 6 movies |
| Proposed facts | 7 |
| Automated eligible drafts | 5 |
| Generation duration, including review | 87.38 seconds |

**The perfect challenge score does not qualify broad automatic generation.** The challenge uses relatively clear contradictions and invented causes; actual paraphrases expose other weaknesses. There are no missing-context or injection cases in this new dataset, and no independent annotations. Token usage is unavailable from the current chat helper. Six films and one run are too small for a reliability claim.

Every generated proposal was separately inspected:

| Film / draft | Inspection |
|---|---|
| Parasite F1 | Withhold: adds a cause not supported by its chosen quote. The critic withheld it, but its explanation also mentions stitching absent from this proposal. |
| Parasite F2 | Supported distinct-take editing detail; retained only as an inspection observation. |
| Spirited Away F1 | Needs citation repair: sentence selection splits at `H.` in Donald H. Hewitt, so the quote starts mid-sentence. The full passage supports the claim, but automated approval missed the incomplete citation. |
| Grand Budapest F1 | Supported research detail; the long list of artists could be shortened. |
| Dune F1 | Supported but withheld. The critic's claim that luminance concerns a material property rather than lighting does not come from the excerpt. |
| Knives Out F1 | Needs wording repair: replace remembering “roles” with remembering character names, keeping the claim closer to its source. |
| Truman Show F1 | Supported acting-research detail; retained only as an inspection observation. |

The sentence bug is in `background_fact_workflow.support_sentences()`, whose period-based expression does not handle personal initials. It is distinct from the honorific fix already made in the authored-bank citation compiler. We deliberately left the writer/critic unchanged during this frozen evaluation so the baseline and existing source-publication fingerprints remain valid.

Full report: `evals/movie-rag/real-film-facts/baseline-v1.json`. Separate inspection and ten-collection/policy preservation evidence: `inspection-v1.json`. Nothing was published. Existing background publisher coverage remains TIME/BFI articles for Arrival; this evaluation does not add six newly qualified source connectors.

Run from `backend` with a new report name:

```sh
.venv/bin/python scripts/evaluate_real_film_facts.py \
  --dataset ../evals/movie-rag/real-film-facts/dataset-v1.json \
  --snapshots ../.cache/source-snapshots \
  --output ../evals/movie-rag/real-film-facts/local-rerun.json \
  --deadline-seconds 360
```

The challenge and generation stages each have the configured deadline; model verification has a separate 30-second bound. The runner preserves failed and unfinished cases, makes no automatic retries and refuses to overwrite an existing report. Rerunning these now-consumed cases is a regression check, not a new unseen benchmark. Private full snapshots are required locally and must match the pinned hashes; they are not committed. The public dataset includes short attributed excerpts and exact revision URLs.

## What to implement next

First repair sentence selection for names and honorifics, and add complete-citation checks. Then test difficult paraphrases and unsupported qualifier/object changes without relying on the same model's acceptance alone. Preserve this baseline and the Dune rejection as development evidence. Use new independently reviewed examples before claiming broader generation quality or expanding automatic publication. Persistent background jobs can follow once this quality path is reliable.

Software validation: all 783 backend checks pass, including 23 new checks for this runner. These checks use controlled inputs and remain separate from the local model results above.
