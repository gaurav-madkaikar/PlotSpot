# Project checklist

Reconciled on 16 October 2026 against the original approved design, subsequent user decisions, current code and evaluation reports.

Original reference: `docs/superpowers/specs/2026-10-07-movie-companion-design.md`. Detailed delivery history: `docs/learning/PROGRESS.md`.

## Original milestones, current status

| Milestone | Delivered | Remaining |
|---|---|---|
| 1. Foundation/UI contracts | Runnable React/FastAPI app, validation, recovery UI, responsive discovery/movie/account views | Advanced profile/recovery screens |
| 2. TMDB and search | Keyword titles/cast/directors/descriptions, conservative spelling suggestions, growing durable catalog, unified live discovery, filters, stable pagination, progressive results, TMDB preview scores and vote counts, Best rated/Highest score ordering, trailers/watch options/related movies | Larger independently labelled relevance evaluation and production load/coverage tuning |
| 3. Embeddings/recommendations | Embeddings/cosine learning exercises and historical evaluations | Semantic search was explicitly retired; do not reinstate it. Personal recommendations based on explicit preferences remain optional future product work |
| 4. Evidence ingestion | Wikipedia, registered screenplays and reviewed publisher articles; provenance, revisions, movie scope, spoiler policy, durable evidence and hybrid RAG retrieval | Broader movie/source coverage and bounded general news discovery with film-identity checks |
| 5. Grounded RAG | Local Ollama discussion, word/vector fusion, conservative story routing, complete-sentence recovery with original-window citation binding, source-backed name/missing-detail context, an evidence-first local support reviewer, abstention, source-specific guardrails, archived baseline and real-model development comparisons | Broader independent support/safety evaluation, stronger entity resolution and review of intermediate extraction/quote quality. Current coverage is registered movies |
| 6. Agent workflows | Purpose-specific fact/story generation, writer/critic verification, budgets, cancellation/recovery and durable internal preparation jobs; shared reviewed facts/quizzes for twenty films; parallel story/article research with partial results and identical-input sequential comparison; durable multi-source HTTP preparation, saved-topic writing, checkpoint replay and explicit reviewed publication with atomic receipts; frozen direct-versus-specialist comparisons, a preregistered direct-first cascade and a 524-candidate generation ablation | Complete the prepared human review, add independent blinded labels for fact/quiz candidates, strengthen semantic verification and widen qualified content/source coverage. Explicit Python orchestration is implemented; LangGraph is not currently a dependency |
| 7. Accounts/community/memory | Temporary guest collections plus email-verified local accounts, HTTP-only revocable sessions, CSRF/Origin guards, durable throttling, owner-scoped collection/spoiler storage, explicit browser import and stale-write protection; movie community threads/replies, author controls, reports and operator moderation; registered-user Facts/Quiz/Discuss | recovery/OAuth/MFA, private notes and deliberate memory |
| 8. Evaluation/CI/portfolio | Deterministic backend/browser CI, separate local-model evaluation commands, archived datasets/policies/traces, a 30-case fresh holdout and quality/cost/latency cascade comparison | Complete blinded human labels, fact/quiz drafting ablation, production load/recovery benchmark, portfolio walkthrough/video and deploy/run documentation |

CI already runs API tests, frontend build and browser journeys. Existing test counts must not be presented as semantic agent accuracy. Earlier reserved evaluation sets have been consumed; future tuning/comparisons need new independent labels. Automatic publication remains limited by observed verification weaknesses.

## Recommended next slices

1. **Independent quality and broader coverage:** a 24-output arm-blinded answer review packet is ready but not yet labelled. The fresh 30-case cascade holdout is consumed and must not be tuned against. The generation ablation is delivered and shows the full specialist pipeline reducing candidate-review work by 64.7% while retaining every published positive; next add blinded semantic labels for a stratified fact/quiz sample. Extend objective story/script and production/news source coverage beyond the current registered films, with manual source review and movie-identity checks.
2. **Delivered research integration; production hardening remains:** multi-source research now runs through durable HTTP jobs, frozen tasks, typed assessment replay and an explicit operator publication CLI. The live Arrival job produced sixteen proposals; assistant source review published one fact/two questions and withheld four other retained candidates. Atomic receipts, compare-and-swap and crash reconciliation protect shared banks; reuse avoids model calls. Consumer drafts stay hidden. Distributed admission, queue history/monitoring, load testing and automated publication qualification remain future production work. See [Lesson 63](learning/63-reviewed-research-jobs.md).
3. **Delivered accounts and durable personal storage:** local accounts, revocable sessions, owner isolation and explicit browser import now preserve All saved and custom memberships in private SQLite storage. Both frontend/backend check identity; revisions reject stale edits. Local email verification is now available with loopback preview or configured SMTP/TLS delivery. Recovery, stronger identity providers, backup/distributed throttling and production load qualification remain future work. See [Lesson 64](learning/64-personal-accounts.md).
4. **Delivered community discussion and member access:** movie-scoped threads/replies, author edit/delete, spoiler redaction, bounded pagination, reporting and operator-only moderation. Facts/Quiz/Discuss now require sign-in at UI and API boundaries. Community comments remain untrusted opinion, separate from factual evidence. Wider abuse detection, moderator operations and production load qualification remain future work. See [Lesson 66](learning/66-community-and-member-access.md).
5. **Delivered account preferences; private memory pending:** saved spoiler defaults and adult-film discovery settings, explicit Save/Reset, revision conflict protection and cross-tab revalidation. Private notes and deliberate memory remain future work. See [Lesson 69](learning/69-account-preferences.md).
6. **Final evaluation and portfolio delivery:** the fresh preregistered cascade comparison records retrieval, support, missing-data, latency, calls and tokens and passed its frozen adoption rule. The fact/quiz generation ablation records critic and readiness value separately. Complete independent human labels before changing live routing, then add a load/recovery benchmark, demo and deployment packaging. Extend the existing CI rather than replacing it.

## Reviewed twenty-film publication — 16 October 2026

Twenty registered films now have explicitly reviewed shared banks. Publication is bound to frozen report, source, workflow, bank and selection identities and records an atomic receipt. The reproducible integrity audit verifies all twenty stored receipts and payload hashes, 113 facts, 215 quiz items (214 scored), 332 citations and two-publisher fact/quiz coverage for every movie. This establishes publication integrity and source diversity, not claim-level semantic accuracy. Independent human labels, single-agent comparison, latency/resource benchmarking and load qualification remain pending. See [Lesson 72](learning/72-reviewed-twenty-film-publication.md) and the [audit report](../evals/movie-rag/expanded-20/published-content-audit.md).

## Direct versus specialist orchestration benchmark — 16 October 2026

The first frozen comparison uses nine objective answer cases from newly published films and three missing/private-data controls. Both arms receive identical cached Wikipedia snapshots, labels, hybrid retrieval, embedding model and answer model; the specialist adds context recovery and a separate support reviewer. Direct RAG passed 8/12 (66.7%) and the specialist passed 9/12 (75.0%). The specialist recovered two direct failures and lost one direct success. It required 2.72× median latency, 58.3% more chat calls and 28.4% more reported prompt/output tokens. Both passed 3/3 missing-evidence controls. Overlapping 95% Wilson intervals and only three discordant pairs make the quality difference inconclusive. One support-review false positive also remains. Independent human claim labels, a larger preregistered set, fact/quiz drafting comparison and multi-user load tests remain pending. See [Lesson 73](learning/73-orchestration-benchmark.md).

## Direct-first cascade benchmark — 17 October 2026

A separate 30-case holdout and routing policy were frozen before execution. Direct passed 26/30, always-specialist 27/30 and the cascade 27/30, with every arm passing all eight missing/private-data controls. Cascade median latency was 4.785s versus 10.221s for always-specialist; chat calls were 41 versus 50. Ten fallbacks included nine abstentions and one generation/validation failure. The preregistered adoption rule passed, but the live application remains unchanged pending the 24-output blinded human review and broader external validation. See [Lesson 74](learning/74-blinded-review-and-direct-first-cascade.md) and the [comparison](../evals/movie-rag/orchestration-benchmark/cascade-comparison-v1.md).

## Fact and quiz generation ablation — 17 October 2026

The frozen twenty-film workflow produced 524 candidates. Critic verdicts alone retained 484, a 7.6% workload reduction. The full specialist path retained 185 ready candidates, a 64.7% reduction, without losing any of the 155 items later selected for publication. Readiness, novelty and corroboration therefore contributed more filtering than the critic alone. Publication conversion is not semantic precision; independent blinded candidate labels remain pending. See [Lesson 75](learning/75-generation-orchestration-ablation.md) and the [generated report](../evals/movie-rag/generation-ablation/funnel-v1.md).

## Explicit scope changes and deferred ideas

- Keyword search replaces mood/story semantic discovery. Its older lessons/reports are learning history.
- Consumer draft workspaces stay hidden by user request. Internal checkpoints are developer infrastructure.
- Adult movies stay searchable until preference-based filtering is added.
- IMDb/Rotten Tomatoes ratings, TV series and streaming playback remain deferred; current TMDB metadata is already shown.
- No fixed 1,500-movie production ceiling. Shared content belongs to movies; quiz attempts, collections and preferences eventually belong to users.
- Distributed queues/caches, large-scale indexing and multi-user load testing are deployment work, not completed production guarantees.

## PlotSpot UI/account polish (12 October 2026)

Delivered viewport-centered trailers, reel branding and PlotSpot copy, count-free Collections navigation, temporary guest saves with a sign-in prompt, and new-account email verification. Preview mode is explicitly local; real delivery requires SMTP configuration. Legacy accounts and shared movie banks remain intact. See [Lesson 65](learning/65-plotspot-verification-and-temporary-saves.md).

## Vote-aware discovery order (13 October 2026)

Best rated now balances score and vote count using a versioned fixed reference. Highest score preserves raw average ordering. Minimum ratings still use the displayed TMDB average; no hidden vote cutoff was added. Sorting occurs before pagination and preserves exact-match relevance. Account preferences have also been delivered. Quiz history and private movie-page history have also been delivered. See [Lesson 68](learning/68-vote-aware-rating-order.md).

## Account preferences delivered — 13 October 2026

Preferences live on the signed-in account page with the existing paper layout and dark footer. Account-owned settings are separate from collections; spoiler defaults permit a movie-level visit override, and adult discovery filters use TMDB flags before ranking/paging with cache and snapshot isolation. Private notes and recovery/OAuth remain separate pending slices; quiz and movie-page history have now been delivered. See [Lesson 69](learning/69-account-preferences.md).

## Private account history delivered — 13 October 2026

Completed quiz rounds have server-calculated scores and replay/retry identity. Successful member movie-page visits are stored with a preference to pause recording; guests, prefetch and section-only navigation do not create visits. Account history is paginated, newest first, and each history can be cleared independently with confirmation. Shared banks and collections remain unchanged. See [Lesson 70](learning/70-quiz-and-movie-history.md).

## Public multi-source evidence delivered — 13 October 2026

DuckDuckGo/Startpage source discovery, bounded full-page acquisition, immutable provenance, optional IMSDb context, shared cache and parallel story/background collection now feed the existing RAG/research workflows. Scripts stay outside facts and cannot be sole released-film authority. Web quiz answers need independent reference support. [Lesson 71](learning/71-multi-source-movie-rag.md) and `evals/movie-rag/multi-source/README.md` record the actual successes and failures. Registered-film eligibility remains; broad automatic content generation is not delivered. Remaining: publisher credibility and conflict handling, fresh independently labelled end-to-end quality/safety comparisons, final-policy generation/load benchmarks and broader qualified movie coverage.
