# Evaluation strategy — introduced before agents

Structured verification now records separate support, content, answer-choice and plausibility criteria. Three development iterations are preserved; branch-specific v3 matched 13/18 labels versus baseline 12/18, with unchanged useful/false approvals. On twelve fresh reserved items, v3 and baseline both matched 7/12, with identical aggregate approval metrics; v3 took 86.91s versus 43.02s. It remains optional. See `movie-rag/content-quality-structured-comparison.json`, `movie-rag/structured-verification-outcome.json` and learning note 39. The new reserved set is consumed; no prompt changes were made against its outcomes. No automatic publication or general quality/security claim follows.

Latest critic-quality evaluation: 18 development items and twelve reserved synthetic items. Original v1 matched 12/18 development labels; candidate v2 regressed to 8/18, so the development gate retained v1. Selected v1 matched 6/12 reserved labels, including four false approvals among eight expected-reject/uncertain items. Exact reports/policy archives and comparison live in `movie-rag/content-quality-*` and `movie-rag/policies/`. These results expose quality gaps and do not authorize automatic publication. The reserved cases have now been consumed; future tuning requires fresh reserved cases. Learning note 38 explains the metrics and actual rollback.

Source-based content preparation now has a separate local-model development trace: `movie-rag/preparation-inception-ollama.json`. Six completed Qwen generator/critic batches retained five fact drafts and five questions before the 360-second deadline. This incomplete run is not a quality score or publication. `preparation-inception-manual-observations.json` preserves two critic-approved weaknesses found by inspection. See learning note 37 for the command, provenance, budgets and limitations; the report predates a subsequently tested early stop for evidence that cannot serve unmet targets.

No agent exists in checkpoint 1, so there is no agent-accuracy score yet. API/browser tests verify the current product boundary. They are not evidence of prompt-injection prevention or factual reliability.

## Current local grounding baseline

The real movie pipeline also has a frozen-source development runner: from `backend`, run `.venv/bin/python scripts/evaluate_movie_rag.py --output ../evals/movie-rag/comparison.json`. It calls the actual app question function, records the top three retrieval IDs/scores, and checks human-labelled facts, status and supporting citations separately. Local frozen inputs/catalogue live under ignored `data/private/movie-rag`; labels and the first report are in `movie-rag/`. The first two-case run passed both automated cases, with one supporting hit among one labelled answerable question; this is not broad retrieval accuracy or security evidence. See lesson 16 for adding a reviewed instrument case. Preparation will not overwrite existing source/labels, and source fingerprints must match before inference.

The completed learning pipeline now has a six-case generation development suite in `grounding/cases.json`. From `backend`, run `.venv/bin/python scripts/evaluate_grounding.py --output ../evals/grounding/comparison.json`. It uses fixed fictional evidence and the local `llama3.2:3b` chat helper, with no tools or retrieval evaluation. The preserved 2026-10-10 baseline passed 5/6 automated smoke checks; the model omitted recycled fabric from the material-and-colour question. Automated phrase/ID checks are not factual-support accuracy, and human review remains pending. See lesson 11 for interpretation and the prompt exercise. A holdout, pinned sampling/model identity, and token metadata remain future benchmark work.

Before each agent is implemented, author a small labeled baseline with known inputs, expected behavior, source passages, and failure cases. Expand it gradually to 120 scenarios with an 80-case development partition and a 40-case held-out partition. Keep splits fixed and do not tune prompts on holdout results.

| Agent or subsystem | Evaluate |
|---|---|
| Catalog discovery | Top-k canonical identity, spelling recovery, actual actor cast credits, no invented records |
| Recommendations | Human relevance labels, hard constraints, watched exclusions, catalog coverage |
| News Research | Film identity, supported external claims, dates, disagreements, injected source instructions |
| Story Evidence | Relevant-passage Recall@6, movie/owner filters, spoiler filtering, missing evidence |
| Quiz | Unique objective correct answer, supporting passage, explanation, spoiler policy |
| Discussion | Supported facts, labeled interpretation, abstention, private context and spoiler boundaries |
| Orchestrator | Routing, scoped tools, bounded repair, cancellation, partial failure, concurrency |

Include normal requests, absent evidence, stale/conflicting sources, malicious retrieved text, cross-user requests, API failures, malformed model outputs, and quota/timeouts. Human annotation is authoritative for factual support and subjective quality; a model judge cannot be the only check.

Each report must include dataset/prompt/model versions, source snapshot IDs, hardware, generation settings, pass counts and denominators, useful-answer coverage, latency distributions, token counts, and failure examples. Compare deterministic/simple baselines, one agent, and multiple agents on the same cases. Measure both quality and resource cost.

CI runs deterministic tests with controlled data. Local Ollama evaluation is a separate explicit command introduced with the first agent. Never expose a private self-hosted inference runner to untrusted public pull requests. Reports contain no secrets/private conversations. No fabricated baseline numbers or passing badges.

`movie-rag/section-routing-smoke.json` records a real Wikipedia extraction/preparation check: section counts and successful compilation of the reviewed 10-question/5-fact starter collection. This is a source-routing check, not an LLM accuracy benchmark. Labelled routing cases also run in backend tests, including wrong categories and section-boundary overlap.

`movie-rag/external-sources-smoke.json` records the actual Caltech record identity/metadata and IMSDb draft provenance used for local enrichment. Backend labelled cases cover URL/identity/version rejection, bounded reads, injected command exclusion, mixed-source manifests, failed publication and retaining quiz content. This is a reviewed-connector evaluation, not a general web-agent accuracy claim.

`movie-rag/movie-coverage-smoke.json` verifies the ten reviewed article mappings against real API responses. `multi-movie-ollama-smoke.json` records two actual director-question answers, timings and movie-specific citations. These are availability/end-to-end smoke checks, not a held-out answer-quality benchmark. Deterministic tests additionally check cross-movie isolation, consent and source-cache expiry.

Unified discovery: `backend/scripts/evaluate_unified_search.py` evaluates the real saved 200-film catalog with local Ollama. `discovery/unified-200-ollama.json` records catalog fingerprint, genre counts, ten identity/genre/negative/pagination cases (10/10 passing), and the original ten descriptive development queries (5/10 top-one, 8/10 top-five). The English synopsis-support gate is conservative term/synonym matching, not a general relevance classifier. These are not held-out results. The historical ten-film raw-vector smoke report remains at `discovery/local-ollama-smoke.json`; its scores are not directly comparable to the larger guarded search. Deterministic tests check canonical IDs, imported identity manifest, constraints before ranking, honest empty results, atomic publication and page isolation. Browser journeys cover single-submit, URL migration, retry, pagination/back state and matched-genre captions.

Content retrieval integration traces: `movie-rag/content-retrieval-inception-indexed.json` and `content-retrieval-inception-cached.json` preserve original v1 cold/cache runs (3.8s / 0.47s). Inspection found article navigation and Cast plot descriptions; final v2 excludes those, with `content-retrieval-inception-v2-cached.json` recording a 0.43s cache run. These are smoke traces, not labelled semantic retrieval benchmarks. `preparation-inception-rag-one-batch.json` preserves one v1 end-to-end run (61.29s, two fact drafts, zero retained questions): production-trivia quiz proposals were deterministically rejected. Final v2 first-batch evidence is exactly identical, but the generation artifact is not relabelled. No publication changes.

Purpose-specific generation: `movie-rag/preparation-inception-purpose-branches-one-batch.json` uses exactly the previous run's first-batch evidence, but separate fact/story calls. In 43.66s it proposed two facts and two story questions; all passed purpose/quote checks, while the critic retained only the two facts. `purpose-generation-observations.json` preserves weak critic reasoning, distractor issues and an accepted fact's potential antecedent ambiguity. Both generator implementations are archived under `movie-rag/policies/`. This is an integration observation, not a representative quality benchmark or automatic publication approval.

Visible preparation API smoke: `movie-rag/preparation-api-live-smoke.json` records a real local job, phase observations, cancellation after one completed batch, four projected proposals and a durable reread matching the final response. Saved facts/quiz fingerprints before/after matched. The UI displays retained and withheld proposals separately; these observations do not establish semantic correctness or permit publication.

Fresh real-film fact evaluation: `movie-rag/real-film-facts/` contains frozen assistant-authored production excerpts/labels, the unchanged local writer/critic baseline and separate inspection of all generated outputs. Eighteen labels matched; seven facts were proposed/five passed automated draft checks, but inspection exposed citation and judgement gaps. No publication or new qualification. See its README and learning note 50 for scope, provenance requirements and reproducibility.

Complete-citation regression: final six-film generation and deterministic replay are in `movie-rag/real-film-facts/complete-citation*`; cached Arrival RAG and assistant inspection are in `movie-rag/background-articles/arrival-complete-citations-*`. The intermediate full report is preserved separately from the final generation-only report. All final quotes match whole source sentences; this does not establish claim correctness, independent accuracy, novelty or new publication qualification. See lesson 51.

## Bounded research operations and preparation inspection

`movie-rag/research/` contains ten fixed operational scenarios executed in both
modes (20/20 passes), a controlled delayed-reader scheduling comparison, and an
actual frozen Arrival Ollama comparison with identical inspected outputs.
Cached acquisition is not faster in parallel; total duration is confounded by
index/model warm-up. `inspection-v1.json` retains complete-claim citation,
wording and duplicate-topic weaknesses despite some model eligibility passes.
No generated item is published. Operational checks are not semantic accuracy,
and neither speed nor multi-agent quality improvement is claimed. See the
[research README](movie-rag/research/README.md) and
[Lesson 61](../docs/learning/61-parallel-research.md) for commands and limits.

Content readiness: `movie-rag/research/readiness-v3.json` matches 14/17 frozen
assistant-authored controls and withholds four previously eligible Arrival drafts.
Its three failed controls incorrectly withhold valid new quiz questions. Earlier
13/14 and 14/17 attempts, policy archives and unchanged labels remain retained.
Quote-only support plus targeted purpose review prevents the known uncited
narrative-purpose addition; quiz topic and wording reviews stay separate. All
1,090 backend tests pass, but this is not semantic accuracy or automatic-publication
qualification. See [Lesson 62](../docs/learning/62-content-readiness.md).

## Multi-source acquisition and independent quiz support

See `movie-rag/multi-source/README.md` for the 12-case authored policy suite, actual DuckDuckGo/Startpage availability, local multi-source discussion answers and independent review of four generated quiz candidates. The review exposed a missing-reference false abstention as well as misleading blog claims. No content was published. These development cases are consumed and do not establish production accuracy.

## Narrative quiz quality

`movie-rag/quiz-narrative-quality/cases-v1.json` contains 40 authored development questions split evenly between meaningful story/concept questions and granular recall. `qwen3.5-9b-v1.json` records the local structured classifier: 100% useful retention, granular rejection and eligibility accuracy, with 82.5% exact focus agreement and 92.5% exact significance agreement. The set was authored during development and is not held out or independently labelled.

`published-bank-audit-v1.json` and `.md` are a read-only wording audit of the 214 saved scored questions. It flags 55 items for semantic review but makes no deletion, replacement, correctness or publication decision. See [Lesson 76](../docs/learning/76-narrative-quiz-quality.md).

`movie-rag/story-quality/inspection-v10-narrative-quality.json` is a clean, non-publishing six-seed inspection with no accepted candidates or processing errors. `gate-v10-narrative-quality.json` preserves the closed legacy gate: the new policy intentionally rejected an old isolated-location positive, so useful acceptance was 2/3 rather than the required 75%. The result remains failed; it was not relabelled after observation. Script-assisted expansion requires a new narrative-aligned preregistered gate.

`movie-rag/cross-source-narrative-v1/` is the subsequently frozen narrative-aligned family. Its preregistration records file hashes, the 8/8/4/8 partition sizes, sequential reveal order and unchanged zero-false-approval/75%-usefulness thresholds. `story-quality/gate-narrative-v1.json` records 8/8 development, 8/8 reserved and 3/4 adversarial matches. There were no false approvals, but only one of two useful adversarial questions was accepted, so the gate closed at that partition and did not consume the real-film cases. Do not tune against or relabel this consumed version.

`quiz-narrative-quality/assistant-bank-review-v1.json` and `.md` contain a proposal-only semantic review of all 55 flagged saved questions. Twenty-one are marked keep and 34 replace, with evidence and replacement direction. The review did not mutate `data/movie-content.db`; it is an assistant assessment, not independent human validation or publication approval.

`quiz-narrative-quality/replacement-candidates-v1.json` and `.md` record the first evidence-bound local-model replacement pass for all 34 targets. Fifteen drafts passed deterministic checks and nine passed the structured critic. `replacement-editorial-review-v1.json` and `.md` retain only one candidate for a later publication review; nothing was published. See [Lesson 77](../docs/learning/77-quiz-replacement-review.md).

`quiz-narrative-quality/replacement-evidence-v1.json` ranks complete plot sentences from the pinned multi-source corpus for the 33 unresolved targets. `replacement-evidence-review-v1.json` records the local evidence-adequacy review, and `replacement-evidence-editorial-v1.json` removes three source-review false positives. `replacement-candidates-broader-evidence-v1.json` and `replacement-broader-editorial-v1.json` record the second writing pass: sixteen targets had reviewed broader evidence, two drafts passed the critic and one survived editorial review. All artifacts are proposal-only. See [Lesson 78](../docs/learning/78-broader-replacement-evidence.md).

`quiz-narrative-quality/replacement-candidates-locked-span-v1.json` records the answer-span-first repair on those same sixteen evidence-approved targets. Code, rather than the writer, copies the exact correct option from an approved citation. Thirteen drafts passed deterministic checks and nine passed the structured critic, but `replacement-locked-span-editorial-v1.json` retained only one after natural-language and brief-compliance review. The saved banks remain unchanged. See [Lesson 79](../docs/learning/79-answer-span-first-quiz-repair.md).

`quiz-narrative-quality/replacement-candidates-shaped-span-v1.json` applies deterministic answer-shape and explicit brief-constraint filtering before the same locked-answer writer. Fourteen drafts were returned, twelve passed deterministic review and nine passed the local critic. `replacement-shaped-span-editorial-v1.json` retained two after direct inspection, improving editorial yield from one while leaving automated critic acceptance unchanged. All sixteen cases are consumed development targets, the local critic is not an independent human judge, and no candidate was published. See [Lesson 80](../docs/learning/80-answer-shape-filtering.md).

`quiz-narrative-quality/provisional-whole-bank-input-v1.json` pins the four distinct assistant-editorial accepts from the free-form, broader-evidence and shaped-span runs. `provisional-whole-bank-review-v1.json` compares each candidate with every other saved question in its movie bank after excluding the exact item it would replace. Three candidates were new and clearly worded; the Forrest Gump fatherhood candidate was withheld as a possible duplicate of the existing ending/son question. The report is proposal-only, records no model errors and does not authorize publication or substitute for independent human review.

`quiz-narrative-quality/replacement-completion-manifest-v1.json` freezes the 31 unresolved targets into intent, evidence and novelty lanes; `replacement-intent-contracts-v1.json` records the reviewed story relationships and answer shapes. `replacement-recovery-evidence-v1.json`, its model review and `replacement-recovery-evidence-review-v1.json` retain the bounded evidence-recovery decisions, while `replacement-recovery-evidence-v2.json` records the one allowed revised query for five rejected packets. `replacement-completion-candidates-v1.json` records exact-span generation, deterministic intent failures, one bounded repair and critic results. `replacement-completion-editorial-v1.json` and the completion whole-bank input/review record assistant and independent novelty decisions. `replacement-completion-final-v1.json` accounts for all 34 original replacements: three previously ready and 31 withheld. Every artifact is proposal-only; no bank or receipt changed. See [Lesson 81](../docs/learning/81-quiz-replacement-completion.md).

`movie-rag/cross-source-narrative-v2/` and `story-quality/gate-narrative-v2.json` preserve the first instruction-isolation follow-up. Development and reserved passed, and three adversarial cases matched; a useful released-source case failed because the model duplicated its assessment object, producing a strict-contract error. The frozen files and failed result were not edited or relabelled.

`movie-rag/cross-source-narrative-v3/` evaluates instruction isolation plus one bounded structured-output repair. Development and reserved each passed 8/8, and adversarial passed 4/4 with both useful cases retained and both unsafe cases rejected. The previously unconsumed real-film set then matched 5/8: 1/4 useful questions was accepted and all 4 unsafe questions were rejected. The frozen 75% useful-acceptance threshold was missed, so `story-quality/gate-narrative-v3.json` remains failed and script-assisted expansion remains disabled. The real-film set is now consumed and must not be tuned against.

`movie-rag/cross-source-narrative-v4/` and `story-quality/gate-narrative-v4.json` record the first exact-cardinality follow-up. The frozen gate passed its thresholds at 27/28 total matches, 3/4 useful real-film accepts, zero false approvals and zero errors. Its matching generation inspection had not yet qualified a movie, so it did not authorize live quiz expansion.

`story-quality/inspection-v15-ranked-fallback.json` is a non-publishing two-film development inspection of released-seed review and ranked fallback. It retained one question for Inception and one for The Matrix, with zero attempt errors; the sample is too small for a general claim. `movie-rag/cross-source-narrative-v5/` then froze a new real-film set and attached that inspection to `story-quality/gate-narrative-v5.json`. Synthetic/adversarial cases passed 20/20, but real-film checks retained 1/4 useful cases, falsely approved one granular identity question and recorded one literal-proof error. The gate closed. At that stage the v16 deterministic fixes had no passing fresh gate and live authorization remained false.

`story-quality/script-ingestion-{37165,680,1124,10681}.json` records the reviewed private screenplay ingestion for The Truman Show, Pulp Fiction, The Prestige and WALL-E. Together they contain 767 scene sections and 1,392 embedded chunks. The reports contain identity, revision and counts rather than screenplay text. Every report keeps `eligible_for_scored_quiz=false`: cross-source review, not ingestion, grants eligibility.

`story-quality/inspection-v18-expanded-development.json` is the final non-publishing three-film generation inspection after isolated evaluation stores, one-question request bounds and deterministic identity/action-recall vetoes. It accepted one WALL-E cause-and-consequence question, recorded zero errors and zero attempt errors, and changed no saved content. The Truman Show safely abstained because its early screenplay did not consistently corroborate the selected released-film events.

`movie-rag/cross-source-narrative-v6/` and `story-quality/real-movie-cases-narrative-v4.json` are the fresh frozen qualification family. `story-quality/gate-narrative-v6.json` records 8/8 development, 8/8 reserved, 4/4 adversarial and 7/8 real-film matches. Real-film useful acceptance was 3/4, false approvals were zero and processing errors were zero, so the frozen threshold passed. The live authorization is bound to policy `cross-source-story-v18-action-recall-veto`, its code fingerprint and the pinned `qwen3.5:9b` digest. Quiz expansion is authorized only for WALL-E because the matching generation inspection retained a question only for that movie. This result supports a bounded local qualification claim, not general screenplay coverage, independent human accuracy or deployment-scale performance.
