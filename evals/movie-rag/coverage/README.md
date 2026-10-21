# Reviewed starter coverage expansion

Two assistant-authored/source-reviewed banks were compiled and published against fixed Wikipedia revisions. Each adds five filmmaking facts and ten scored story questions. Complete saved coverage now spans six films; metadata coverage is a separate larger collection.

- `knives-out-publication.json`: preparation report, TMDB 546554.
- `truman-show-publication.json`: preparation report, TMDB 37165.
- `live-publication.json`: source/bank hashes, reviewed item/answer identities, live feature inventory, spoiler protection, repeat-read equality and preservation of the original four collections.

No Ollama generation calls were made for these starter banks. Automated tests check contracts, extraction and failure behavior; source review checked claims and options. This is not a held-out semantic benchmark or proof of automatic publication quality. Existing generated/story RAG gates remain separate.

Full snapshots and SQLite database are ignored private local artifacts. Reproduce from backend with:

```sh
.venv/bin/python scripts/prepare_movie_content.py --movie-id 546554 --source-snapshot ../.cache/source-snapshots/546554.json --report ../evals/movie-rag/coverage/knives-out-publication.json
.venv/bin/python scripts/prepare_movie_content.py --movie-id 37165 --source-snapshot ../.cache/source-snapshots/37165.json --report ../evals/movie-rag/coverage/truman-show-publication.json
```

An existing collection is retained by default; replay reports change to `retained`. Refresh is explicit, requires compilation and warrants fresh content review.

## Ten-film completion

Four more authored/source-reviewed banks add twenty facts and forty scored questions: 496243 (Parasite), 129 (Spirited Away), 120467 (The Grand Budapest Hotel), 438631 (Dune 2021). Each `[movie_id]-publication.json` records the explicit publication against its exact source revision. `ten-film-live-publication.json` records code/data review evidence, source/bank hashes, full ten-film inventory, equal live reads, spoiler protection, stored/compiled equality and original-six preservation. New publications use reviewed-multi-movie-v2.

No Ollama calls were made. Automated source/compiler/UI checks plus assistant source review remain distinct from unseen model-quality evaluation. Story generation qualification and publisher article source coverage are unchanged.

## The Dark Knight (12 October 2026)

Movie 155 adds five assistant-authored/source-inspected filmmaking facts and ten scored story questions, extending shared saved coverage to eleven films. `155-publication.json` records publication; `dark-knight-publication-review.json` records the exact revision, source/bank hashes, item review and unchanged original-ten hashes. `dark-knight-live.json` records readiness, consent, equal repeated reads and a real HTTP discussion answer.

The bank used no generation calls. A separate real local-Ollama development inspection runs the shared Wikipedia question function with five expectations frozen before inference. `dark-knight-discussion-cases.json` holds those labels and `dark-knight-discussion-v1.json` holds the outputs/model digests/prompt and pipeline hashes. Three of five automated checks passed. The Dent-decoy question missed its supporting plot passage and safely abstained. The ending answer cited a useful thematic-analysis passage omitted from the pre-run plot-only support labels, as well as an unnecessary citation. Assistant inspection records this annotation limitation without changing labels or the original failed grade. This is neither an independent holdout nor an automatic-publication qualification.

From backend, reproduce with the inspected private snapshot (or explicitly fetch/review the registered article before preparation):

```sh
.venv/bin/python scripts/prepare_movie_content.py --movie-id 155 --source-snapshot ../.cache/source-snapshots/155.json --report ../evals/movie-rag/coverage/155-publication.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/dark-knight-discussion-cases.json --output ../evals/movie-rag/coverage/dark-knight-discussion-rerun.json
```

The original snapshot is required for these labels; a changed revision requires new reviewed labels. The runner validates identity, full snapshot fingerprint and passage IDs before model I/O. A failing case produces a saved report and exit status 1. No script/news source or more-question generation gate was enabled for this movie.

## Discussion retrieval and citation comparison

`discussion-retrieval-review.json` combines the latest `*v6.json` reports:
seventeen cases across The Dark Knight, Arrival and Knives Out. The original five
expectations are untouched; `discussion-transfer-*-cases.json` adds twelve
assistant-source-inspected expectations frozen before their first model runs.
`discussion-transfer-label-review.json` records label authorship and limitations.
All are now consumed development data, not independent holdouts.

The candidate combines BM25 and vector ranks with conservative plot routing.
Generation selects verbatim support options offered in both prompt and schema;
code validates location and binds source IDs. Both retrieval and generation
change, so this is a full pipeline comparison, not a retrieval-only ablation.
The archive in `vector-baseline-v1` preserves the previous pipeline/prompt.
Both arms use the same snapshots, chunks, labels and local model digests and
alternate execution order without overlapping inference.

Latest automated results: **15/17 candidate, 11/17 baseline**. Annotated support
hit at three: **14/14 versus 11/14** answerable cases. Both abstain appropriately
on all three labelled missing-data cases. Neither arm has response-validation
errors in this final run. Candidate median duration was **4.894s**, baseline
**1.708s**; these warm sequential observations include extra prompt/schema
content and are not a throughput benchmark.

The makeup answer still cites an incomplete continuation instead of the
retrieved setup. The ending answer's supported paraphrase fails the unchanged
hero/faith/hope phrase check. Some passing cases contain extra excerpts/citations.
The assistant inspection separates these limitations without changing labels,
historical grades or the runner's pending independent review fields. Literal
quote presence is not semantic entailment or qualification for publication.

Reports v1–v5 retain the attempted variants: ID aliases, free-copy quotes and
schema-only options exposed wrong bindings, malformed copies and unnecessary
validation failures. The final prompt explicitly shows excerpt choices; repeated
valid excerpts normalize to one citation. There are no automatic model retries.

From backend, run a comparison with the exact private snapshot:

```sh
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/dark-knight-discussion-cases.json --compare --output ../evals/movie-rag/coverage/dark-knight-discussion-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/329865.json --dataset ../evals/movie-rag/coverage/discussion-transfer-329865-cases.json --compare --output ../evals/movie-rag/coverage/arrival-discussion-new-run.json
.venv/bin/python scripts/evaluate_grounding.py --output ../evals/grounding/discussion-new-run.json
```

The separate six-case fixed-evidence grounding report is
`evals/grounding/discussion-options-v6.json` (6/6 automated checks). It does not
evaluate retrieval or universal injection resistance. The HTTP smoke report is
`discussion-retrieval-live.json`. Saved banks and existing script qualification
remain unchanged. See lesson 58 for the complete learning walkthrough.

## Complete discussion sentences and support review (Lesson 59)

`discussion-support-review.json` inspects the final four `*-sentences-v2.json`
reports. They compare the frozen Lesson 58 **hybrid** baseline with complete
sentence recovery and a distinct local Qwen support reviewer. This is a new
comparison boundary: use `--compare-current`, not the vector-baseline `--compare`.
Both arms retain the same sources, original chunks/embeddings, unchanged
seventeen labels and `llama3.2:3b` generator. Local inference remains sequential.

Final automated grades: **16/17 candidate versus 15/17 baseline**. Annotated
support hit-at-three is **14/14** in both arms; expected abstentions pass **3/3**
in both. No response-validation errors occurred. The recovered makeup sentence
is bound to both original windows 073 and 074. Arrival's future-visions answer
is rejected because the selected context uses Banks while the question uses
Louise and omits the most explicit premonitions sentence. Its failed positive
grade remains unchanged. Some passing answers contain unnecessary citations or
details beyond their selected sentences; a pass is not full claim entailment.

Whole-pipeline medians: **8.018s candidate, 2.729s baseline**. These alternating
sequential local observations include model loading/swapping and are not isolated
reviewer latency or production throughput measurements.

`evals/grounding/support-review-cases.json` froze twelve assistant-authored
controls before their first inference. Current `support-review-qwen-v4.json`
matches **11/12**, including **one false acceptance** of a wrong causal reason.
Earlier prompt/model reports are retained. These repeatedly tuned controls are
development evidence, not a holdout or universal injection-defense benchmark.

The first `sentences-v1` reports were produced while a canonical-anchor validation
guard was added on disk. Their end-of-run context hash does not attest the loaded
pre-guard source. Outputs and labels are preserved as historical observations;
the complete comparison was rerun with frozen final code as `sentences-v2`. The
aggregate inspection records this provenance limitation.

From backend, using the private frozen snapshots and installed local models:

```sh
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/dark-knight-discussion-cases.json --compare-current --output ../evals/movie-rag/coverage/dark-knight-sentences-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/discussion-transfer-155-cases.json --compare-current --output ../evals/movie-rag/coverage/dark-knight-transfer-sentences-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/329865.json --dataset ../evals/movie-rag/coverage/discussion-transfer-329865-cases.json --compare-current --output ../evals/movie-rag/coverage/arrival-sentences-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/546554.json --dataset ../evals/movie-rag/coverage/discussion-transfer-546554-cases.json --compare-current --output ../evals/movie-rag/coverage/knives-out-sentences-new-run.json
PYTHONPATH=src .venv/bin/python scripts/evaluate_discussion_support.py --output ../evals/grounding/support-review-new-run.json
```

Use new report paths for additional runs; do not overwrite historical outputs.
A failed case exits 1 after saving the report. Article revisions must match the
frozen labels. Public reports retain bounded selected evidence, hashes and model
digests; full source snapshots remain private. Support-control runs require
`qwen3.5:9b`; movie runs additionally require `nomic-embed-text:v1.5` and
`llama3.2:3b`. No model is downloaded automatically.

`discussion-support-live.json` records actual HTTP/UI smoke verification. All
eleven saved banks and the independent script policy/Inception expansion gate
are preserved. No automatic publication or script qualification is granted.
See [Lesson 59](../../../docs/learning/59-discussion-support.md).

## Identity and requested-relation support (Lesson 60)

The baseline in `support-baseline-v1` preserves Lesson 59's context, generation
and two-field review modules. Use `--compare-support` to compare it with the
current name-context and evidence-first review flow. Top-three retrieval and
expanded generation IDs are recorded separately for both arms.

`support-relations-cases.json` adds eight fictional name/reason controls to an
unchanged copy of the historical twelve. All expectations were frozen before
candidate outputs. They are assistant-authored development controls, not an
independent human-labelled holdout. `support-relations-v5.json` records the first
20/20 reviewer result. The first `*-relations-v1.json` movie reports still fail
Arrival: the reviewer sees the name sentence but the generator omits explicit
premonitions/unborn-daughter support. Outputs and labels remain unchanged.

The final candidate additionally recovers at most one exact offered sentence
containing two missing answer terms. It stays within the original eligible pool,
revalidates source coverage and carries its IDs into final citations. Lexical
coverage is not approval: the reviewer still checks support. At most five
bounded review sentences and three final citations; overflow abstains. No extra
embedding or model call is added.

From backend, after installing the existing local model tags, reproduce with
new report paths and the exact private frozen snapshots:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_discussion_support.py --dataset ../evals/grounding/support-relations-cases.json --output ../evals/grounding/support-relations-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/329865.json --dataset ../evals/movie-rag/coverage/discussion-transfer-329865-cases.json --compare-support --output ../evals/movie-rag/coverage/arrival-relations-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/dark-knight-discussion-cases.json --compare-support --output ../evals/movie-rag/coverage/dark-knight-relations-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/155.json --dataset ../evals/movie-rag/coverage/discussion-transfer-155-cases.json --compare-support --output ../evals/movie-rag/coverage/dark-knight-transfer-relations-new-run.json
.venv/bin/python scripts/evaluate_registered_movie_rag.py --source-snapshot ../.cache/source-snapshots/546554.json --dataset ../evals/movie-rag/coverage/discussion-transfer-546554-cases.json --compare-support --output ../evals/movie-rag/coverage/knives-out-relations-new-run.json
```

Do not modify evaluated module files while a run is active. The runner records
initial module hashes and `code_changed_during_run`; a changed-code report
cannot attest the final disk files as the imported pipeline. No report grants
publication or production qualification. Read
[Lesson 60](../../../docs/learning/60-discussion-relations.md) for the code flow.

Final `*-relations-v2.json` comparisons: 17/17 candidate versus 16/17 frozen
Lesson 59 baseline; both annotated support retrieval 14/14 and abstention 3/3.
Whole-pipeline median durations are 13.494s versus 8.336s, not throughput claims.
All recorded initial module hashes match final files and code did not change
during these runs. Final reviewer controls `support-relations-v6.json`: 20/20.
The aggregate source inspection retains the reviewer's imperfect quote subset
and the earlier Arrival failure in `discussion-relations-review.json`.

`discussion-relations-live.json` records four passing HTTP smoke cases and the
existing Arrival UI's answer plus both expanded revision-backed source cards.
All eleven banks, script policy and Inception expansion gate remain unchanged.
The temporary UI tab was closed with its initial spoiler preference preserved.
These consumed assistant-authored development results do not qualify production
support accuracy, safety or source publication.
