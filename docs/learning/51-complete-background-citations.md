# 51. Keeping generated citations complete

The previous fact inspection found a correct dubbing claim accompanied by an incomplete citation. Our regular expression treated the period in **Donald H. Hewitt** as the end of a sentence. The model selected the remaining fragment, and the critic accepted it. This was a citation defect even though the full article supported the claim.

## The fix belongs in code

A stronger prompt would still let the model choose a broken sentence ID. Instead, `sentence_spans.complete_sentence_spans()` computes exact start/end offsets into the original source text. Known titles, personal initials, dotted abbreviations and decimals stay inside the sentence. Headings and unfinished trailing fragments do not become supporting sentences.

Quotes are direct slices such as `source_text[start:end]`. We never repair punctuation or reconstruct a person's name in a quote. This preserves the evidence exactly as it appeared.

The helper is deliberately conservative English punctuation logic. It can merge sentences at an ambiguous abbreviation or decline valid evidence; it does not establish grammar, factual truth or complete context. Quoted speech, unfamiliar abbreviations and other languages need broader coverage before relying on this across arbitrary internet pages.

## Three places use the result

**Retrieval:** `article_evidence()` computes sentence boundaries in a whole source section, then keeps only complete sentences lying inside a retrieved window. If a 600-character window starts in the middle of a sentence, the incomplete beginning is excluded. Splitting the window alone would hide the missing beginning.

**Generation inspection:** `support_sentences()` assigns short complete quotes code-owned IDs such as `S1`. The writer selects an ID, and code attaches the original text. `complete_support_quote()` independently checks that the returned quote is still one of those complete sentences. A model's approval cannot bypass that check.

**Explicit publication:** `complete_source_quote()` checks the entire original source section and requires the chosen complete sentence to lie inside the recorded evidence span. Checking only a supplied passage would be insufficient: a forged passage could start at “Hewitt” and make the remaining fragment look complete. The full-source check rejects that attempt before any write.

A complete sentence can still contain a wrong claim or lack an antecedent. The separate critic and operator/assistant source inspection remain necessary. We kept writer/critic prompts unchanged in this slice; the Dune judgement and subtle wording drift from lesson 50 need their own future work.

## Why the fingerprint changes

The background workflow's fingerprint now includes `sentence_spans.py`. Changing its rules changes the evidence a model sees, so an inspection from an older version cannot authorize publication under the current version. Previous reports and the earlier workflow are preserved for comparison. Existing saved collections remain readable; this code change does not rewrite their content.

This is similar to using an ingredient list when comparing recipes: if the inputs changed, yesterday's result does not automatically describe today's preparation.

## Tests versus model reruns

Controlled tests reproduce the exact initial-splitting defect, decimals, titles, quoted punctuation, footnotes, clipped retrieval windows, and forged publication origins. They also simulate a critic approving a fragmented quote and verify that code still withholds it. These tests should be stable and fast without Ollama.

The local Ollama rerun checks actual output behavior on the six previously consumed film excerpts. These are regression/development observations, not new held-out accuracy. Separately, cached TIME/BFI Arrival sources exercise real Chroma retrieval, quote selection and writer/critic review. Neither inspection automatically publishes its drafts.

A deterministic replay additionally caught Wikipedia’s `[a]` footnote marker merging two sentences. The final parser recognizes numeric and single-letter reference markers without editing quote bytes. Replaying the original seven outputs now withholds only the actually fragmented Spirited Away quote; valid citations retain their original boundaries. A final source-boundary check is necessary even when a passage-level check succeeds.

Validation: 804 backend checks passed. No frontend changes or application restart were needed.

## Actual results and preserved reports

The intermediate full challenge rerun still matched **18/18** consumed labels (six useful approvals, no flawed approvals out of twelve negatives). Those critic cases do not exercise the new sentence parser; the critic prompt was unchanged. After the lettered-footnote correction, we reran **generation only** with the final code, avoiding another identical challenge call. The report's mode explicitly records this and includes no copied labelled score.

| Final inspection | Result |
|---|---:|
| Six-film generation | 6 / 6 movies completed |
| Proposed facts | 7 |
| Quotes matching a whole original source sentence | 7 / 7 |
| Automated eligible drafts | 5 |
| Model/contract errors | 0 |
| Generation and review time | 83.50 seconds |
| Cached Arrival RAG | 4 candidates, 1 eligible draft, 0 errors |
| Arrival RAG time | 48.53 seconds |
| Published items | 0 |

The Spirited Away output now cites the whole sentence beginning **“Screenwriters Cindy Davis Hewitt and Donald H. Hewitt…”**, instead of the fragment starting **“Hewitt penned…”**. The source and vector snapshots did not need rebuilding: their text did not change. Arrival reused both publisher snapshots and both Chroma indexes; local query embedding and chat calls still ran.

Every generated proposal was inspected. Counts alone hide important limits:

- The six-film writer still adds an unsupported cause to one Parasite draft; the critic withholds it. Its explanation contains an inaccurate reference to stitching, which that draft does not mention.
- Knives Out still changes remembering character names into remembering roles. Complete citations do not fix this wording drift.
- Dune remains withheld with an unsupported material-versus-lighting distinction in the critic's reason.
- The Arrival writer invented **Roger Deakins** where the excerpt named **Young**; the critic rejected it.
- An Arrival Turrell proposal resolves “both men” to the designer and director, but supplies a full director name absent from the retrieved excerpt. The whole cached article identifies Villeneuve. This is a support-context gap, not a demonstrated false attribution; the duplicate gate also withholds the draft.
- The two other withheld Arrival drafts overlap saved wording. One vocal-technique draft passes the checks; this does not establish semantic novelty or permission to publish.

These are consumed development/integration observations, not representative accuracy, security coverage or throughput. A model can still invent details using a perfectly complete quote. The quote guard is a necessary check, with separate semantic judgement and source inspection still required.

Reports:

- `evals/movie-rag/real-film-facts/complete-citations-v2.json`: intermediate full challenge/generation before the letter-footnote correction.
- `complete-citation-replay-v2.json`: preserved deterministic replay exposing the lettered-footnote issue.
- `complete-citation-replay-final.json`: final deterministic replay correctly withholds only the fragmented baseline quote.
- `complete-citations-final-generation.json`: actual final six-film generation with current fingerprints.
- `complete-citations-comparison.json`: inspection of all seven final outputs and before/after quote.
- `evals/movie-rag/background-articles/arrival-complete-citations-v2.json`: actual cached RAG under the final policy.
- `arrival-complete-citations-inspection.json`: inspection, report hash and saved-content/story-policy preservation evidence.

All ten saved collections and story policy remained unchanged. The background policy is now `reviewed-background-rag-v2-complete-citations`, with its helper included in the fingerprint. Archived old reports cannot authorize new publication under the changed code. The consumer UI still shows saved content.

Reproduce generation without repeating the labelled critic challenge, from `backend`:

```sh
.venv/bin/python scripts/evaluate_real_film_facts.py \
  --dataset ../evals/movie-rag/real-film-facts/dataset-v1.json \
  --snapshots ../.cache/source-snapshots \
  --output ../evals/movie-rag/real-film-facts/new-generation-run.json \
  --generation-only
```

To inspect the cached publisher RAG, use a new report filename, omit `--refresh` and `--selection`, and run `scripts/prepare_background_facts.py --movie-id 329865 --report <new-report.json>`. Its existing inspection command does not reserve report paths, so choose a new name yourself. The six-film runner refuses existing report paths.

Next: improve entity/context support and exact claim wording, measure those difficult cases separately, then expand reviewed sources and add persistent jobs for long inference. Quote correctness is fixed for the reproduced cases; broad automatic fact generation is not qualified by these results.
