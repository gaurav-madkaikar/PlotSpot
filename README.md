# PlotSpot

A learning-first movie discovery and discussion application. The application is called **PlotSpot**.

## Current checkpoint: progressive discovery and multi-movie discussion

Working: one debounced keyword search for titles, actors, directors and saved descriptions; saved title/description matches appear before bounded live TMDB discovery completes in the same grid. Completed results own stable pagination; actor/director membership still requires verified identities. The catalog grows beyond its initial 1,500-film seed. Search supports conservative spelling corrections, person clarification, strict genre/runtime/language filters, posters, metadata, trailers, watch options and browser-local named collections. Offline demo mode uses ten authored films.

Catalog preparation persists enriched search metadata. Live discovery stores lightweight IDs, titles, years, posters, synopses, genres and language; missing runtime is fetched when a runtime filter requires it. Full credits, cast/characters and presentation metadata load on opening a movie. Prepared lexical indexes reuse normalized fields and invalidate after database writes. Search does not fetch scripts or prepare RAG/content collections. Earlier embedding preparation is retained as learning history, not active search behavior.

Twenty films now have persistent, explicitly reviewed source-backed collections in **Quiz** and **Facts**. These read from local SQLite after spoiler consent, survive restarts and require no generation on viewing or replay. Every published bank has at least five facts and ten scored questions with at least two publisher families for each content type. The [published-content audit](evals/movie-rag/expanded-20/published-content-audit.md) verifies receipts, payload hashes, counts and source diversity; it does not claim that every answer is semantically correct. Unsupported movies disclose unavailable collections.

The Dark Knight adds five inspected production facts, ten scored story questions and a registered Wikipedia discussion source. Its starter bank is assistant-authored; a separate five-case real-Ollama development inspection passed three automated checks and exposed a story-retrieval gap plus incomplete supporting-passage labels. These are not production accuracy claims. [Lesson 57](docs/learning/57-dark-knight-coverage.md) explains the publication, real outputs and limits.

Wikipedia discussion now combines scoped word/vector retrieval, complete source sentences, source-backed name context and a separate evidence-first local reviewer. It can recover one missing-detail sentence from the existing eligible pool while preserving original citation IDs and budgets. The final development comparison passes 17/17 checks versus 16/17 for the frozen Lesson 59 pipeline; twenty fictional reviewer controls pass. Median local duration is 13.494s versus 8.336s. These small assistant-labelled development results are not production or safety qualification, and reviewer quote selections can still be incomplete. [Lesson 60](docs/learning/60-discussion-relations.md) and the [inspection report](evals/movie-rag/coverage/discussion-relations-review.json) explain the stages, failures and limits. Earlier retrieval/context comparisons remain in [Lesson 58](docs/learning/58-discussion-retrieval.md) and [Lesson 59](docs/learning/59-discussion-support.md).

Arrival now includes eight saved facts and twelve story questions, with reviewed TIME/BFI production sources and dated reading links. The latest durable local-Ollama research job added one source-inspected production fact and two unused plot questions through an explicitly reviewed selection. Interstellar includes the reviewed CaltechAUTHORS fact and research links; screenplay context is confined to story/discussion workflows. [Lesson 47](docs/learning/47-background-article-rag.md) explains article ingestion; [Lesson 63](docs/learning/63-reviewed-research-jobs.md) explains the new durable pipeline and publication receipt. These examples establish a working source path, not automatic generation across the catalog.

Durable HTTP preparation now uses independent story and production researchers, bounded parallel source reads, purpose-scoped RAG, saved-topic-aware writing, typed critics and readiness checks. Local model calls remain serial. Complete banks are reused without inference; explicit refresh checkpoints tasks for restart. Movie views keep reading the last published bank. An operator CLI pins a reviewed selection to its report/source/policy/bank identities and commits content with an idempotent audit receipt. Consumer drafts stay hidden. See [Lesson 63](docs/learning/63-reviewed-research-jobs.md) and the [research reports](evals/movie-rag/research/README.md).

A frozen twelve-case local benchmark now compares direct single-agent RAG with the current context-recovery/support-review pipeline on identical evidence, retrieval and model settings. The direct arm passed 8/12 and the specialist arm 9/12; both passed all three missing/private-data controls. Specialist median latency was 9.642s versus 3.540s, with 19 versus 12 chat calls. The one-case gain is inconclusive on this small non-human-labelled set, and one reviewer false positive remains. See [Lesson 73](docs/learning/73-orchestration-benchmark.md) and the [comparison report](evals/movie-rag/orchestration-benchmark/comparison-v1.md).

A fresh preregistered 30-case benchmark now evaluates a direct-first fallback policy. Direct passed 26/30, always-specialist 27/30 and the cascade 27/30; all passed 8/8 missing/private-data controls. The cascade matched specialist quality with 4.785s versus 10.221s median latency and 41 versus 50 chat calls. A 24-output arm-blinded human-review packet is ready, so this result has not changed the live Discuss path yet. See [Lesson 74](docs/learning/74-blinded-review-and-direct-first-cascade.md) and the [cascade report](evals/movie-rag/orchestration-benchmark/cascade-comparison-v1.md).

The frozen generation ablation audits 524 writer candidates from the twenty-film workflow. The critic alone reduced review work by 7.6%; the full critic/readiness pipeline reduced it by 64.7% to 185 candidates and retained all 155 later publication selections. This measures filtering and reviewer workload, not semantic accuracy. See [Lesson 75](docs/learning/75-generation-orchestration-ablation.md) and the [generation report](evals/movie-rag/generation-ablation/funnel-v1.md).

Final consumed readiness controls match 17/17, repairing the three known valid-question failures. Six fresh fictional pairs with blinded independent AI labels match 4/6; a real generated question also passed automated review with a wrong Banks/China attribution and was withheld during explicit source inspection. The system therefore requires reviewed publication; these results do not establish production model accuracy or safety. All 1,120 backend checks, 17 affected browser checks and the frontend build pass. Tests verify code contracts and failure recovery separately from model quality.

Not implemented yet: unrestricted automatic quiz/fact publication, general movie-news ingestion, community posting. Agent/RAG preparation remains bounded and internal. Unified search uses `/api/search/catalog`; the older `/api/search` and `/api/search/names` routes remain compatible but are not separate consumer result panels.

Demo artwork is original abstract illustration, not official movie posters. Summaries are manually authored introductions. Guest saves clear on refresh; signed-in collections persist privately in the backend.

## Run locally

Requirements: Node 22.12+ or a compatible newer release, npm, uv, and Python 3.12. Movie browsing works without Ollama. Live Wikipedia Discuss answers require local Ollama with `nomic-embed-text:v1.5`, `llama3.2:3b` and `qwen3.5:9b` installed. Internal fact/quiz preparation uses its configured local models; keyword search invokes no model. The app does not download models automatically.

From this directory, in the first terminal:

```sh
cd backend
uv sync --extra dev
uv run uvicorn movie_companion.main:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs. The development frontend proxies `/api` to the backend, so no broad CORS policy is needed.

To try the features, open `/movies/157336`, allow spoilers, and open **Quiz**, **News & facts**, or **Discuss → Ask PlotSpot**. Discuss’s first source preparation may take longer; its document vectors persist locally in ignored Chroma storage. Quiz and Facts use saved SQLite content. See [the saved-content walkthrough](docs/learning/18-prepared-movie-content.md).

If uv cannot write its default cache, prefix its commands with `UV_CACHE_DIR=/private/tmp/movie-companion-uv-cache`. If npm cannot write its cache, use `npm --cache /private/tmp/movie-companion-npm-cache ci`.

### Enable live data

Copy `backend/.env.example` to `backend/.env` and edit it locally:

```dotenv
MOVIE_DATA_SOURCE=tmdb
TMDB_READ_TOKEN=your_local_api_read_access_token
```

Use the **API Read Access Token**, not the shorter API key, from your [TMDB account API settings](https://www.themoviedb.org/settings/api). Never put it in frontend variables or commit it. The local file is ignored by Git; environment variables override it. Restart the backend after configuration changes. Set `MOVIE_DATA_SOURCE=demo` to return to offline mode. Invalid/missing live credentials return a configuration error; live failures do not silently substitute demo records.

Live mode uses read-only HTTPS requests, an 8-second request timeout, a 30-second search budget, at most four upstream requests at once, and a ten-minute/256-entry in-memory cache. Cache contents expire or disappear on restart. No automatic retries are made upstream. UI language stays English; the language filter matches the movie's original language. The current dropdown exposes English/Korean/Japanese; other-language titles can still appear when no language filter is applied.

This product uses the TMDB API but is not endorsed or certified by TMDB. Attribution is also included on the application's About page, with an official TMDB logo. TMDB is [free for non-commercial use with attribution](https://developer.themoviedb.org/docs/faq).

## Verify

```sh
cd backend
uv run pytest
```

```sh
cd frontend
npm run build
npm run test:e2e
```

Browser tests start their own local servers. Install the project-local test browser once with `npm run browsers:install` if needed. Stop any manually started servers on the test ports first. No API keys or inference service are required for these checks.

### Inspect AI reliability locally

PlotSpot includes a read-only, developer-only **AI Reliability Lab** for inspecting registered evaluation reports and bounded recent pipeline runs. It is deliberately absent from production builds and has no public navigation link.

Set both local flags to `true`:

```dotenv
# backend/.env
PLOTSPOT_LAB_ENABLED=true

# frontend/.env.local
VITE_PLOTSPOT_LAB_ENABLED=true
```

Restart both servers, then open `http://127.0.0.1:5173/lab`. The backend flag is authoritative: when it is disabled, all lab API routes return `404`. The frontend flag only exposes the development route. The lab reads a fixed registry of evaluation artifacts and a bounded projection of local run records; it cannot launch jobs, alter reports, publish content or reveal prompts, retrieved passages or model reasoning. See [Lesson 82](docs/learning/82-ai-reliability-lab.md) for the full data flow and safety model.

## Learn alongside the implementation

Start with [Checkpoint 1](docs/learning/01-foundation.md). It traces one request from search field to Python and back, provides a small exercise, and explains the design decisions.

The learner completed [language filtering](docs/learning/02-language-filter.md) and the first TMDB mapper. Our pairing workflow is now: the learner implements one representative piece, we review it, then the assistant extends and verifies the feature. Read [the live-data walkthrough](docs/learning/03-tmdb-integration.md) to follow how the mapper connects to the client, backend routes, and UI.

- [Approved project design](docs/superpowers/specs/2026-10-07-movie-companion-design.md)
- [Milestone 1 implementation checklist](docs/superpowers/plans/2026-10-07-foundation.md)
- [Evaluation strategy](evals/README.md)
- [Design system](design-system/movie-companion/MASTER.md)

## Repository boundaries

`backend` owns validated movie records and search behavior. `frontend` owns rendering and interaction. `evals` owns datasets and measured agent behavior. `docs/learning` explains concepts and holds learner exercises. No remote repository, paid services, telemetry, or secrets are configured.


Prepare saved content once from the backend directory with `.venv/bin/python scripts/prepare_movie_content.py`. Existing published content is retained across preparation-version upgrades without source/model calls; `--refresh` explicitly prepares a replacement. Saved content is local and not committed. See [prepare-once walkthrough](docs/learning/18-prepared-movie-content.md).

New Wikipedia ingestion preserves article sections. Chunks cannot cross headings; starter quiz preparation uses Plot, while facts use production/casting/filming/music/effects evidence. Unclassified sections remain available to Discuss. Classification is conservative and does not imply spoiler safety. Existing saved content remains available; a refresh requires a new section-aware source. See [section routing](docs/learning/19-section-aware-evidence.md).

Enrich an existing saved Interstellar collection from the backend directory with `.venv/bin/python scripts/prepare_external_sources.py`. This fetches two fixed reviewed sources, adds the sixth fact and reading links, and retains all quiz questions. Subsequent runs reuse the saved content; its `--refresh` rechecks external sources without replacing the quiz. Early/unverified screenplay drafts are excluded from quiz evidence. See [external source walkthrough](docs/learning/20-reviewed-external-sources.md).

Source-backed **Discuss** is registered for the same twenty-film set. Each film uses an explicit reviewed movie-to-Wikipedia mapping and can also use its qualified cached public sources. Feature availability is read from the backend. Sources exclude reference lists and retain revision/spoiler metadata and movie-scoped retrieval. Earlier real local-model checks answered director questions for Arrival and The Truman Show with correct article citations; those smoke checks are not a general quality benchmark. See [multi-movie discussion](docs/learning/21-multi-movie-discussion.md) and [the expanded publication lesson](docs/learning/72-reviewed-twenty-film-publication.md).

### Keyword search and persistent catalog

**Find your next film** searches saved titles, alternative titles, cast, directors and description keywords. Exact title/person matches rank first. Every other result needs literal metadata support for all query keywords; spelling corrections are bounded and ambiguous corrections are withheld. Suggestions link known titles, actors and directors to verified movie IDs. Genre, language, runtime and pagination remain strict.

Search reads SQLite metadata and merges bounded TMDB title/person discovery even when local matches exist. Shared five-minute query snapshots freeze ordering before pagination; discovered metadata persists. Ambiguous people are clarified above the same grid, and partial provider failures retain usable matches; failed searches with no movies offer retry. `/api/discover` is retired (410). See [Lesson 55](docs/learning/55-unified-movie-discovery.md) for discovery and [Lesson 56](docs/learning/56-progressive-search.md) for concurrent local/completed responses, prepared indexes and lightweight tiles. The [current checklist](docs/PROJECT_CHECKLIST.md) reconciles original milestones with later scope changes.

### Accounts and personal collections

Use **Sign in** to create an account with username, email and password. New accounts require email verification before login. Signed-in collections and spoiler/watched state persist in an owner-scoped backend database; guests hold temporary saves in page memory that clears on refresh. **Keep these saves** on `/collections` explicitly merges the current visit’s saves into the account and clears the temporary copy. All saved and multiple custom memberships retain their existing behaviour. Facts/quizzes remain shared by movie. **Facts, Quiz and Discuss require sign-in**; guests can continue browsing movie metadata and saving films temporarily. Discuss now includes member threads/replies, spoiler labels, author edit/delete controls and reporting. Moderator report review is enabled only for account IDs in `PLOTSPOT_MODERATOR_IDS` (empty by default). See [Lesson 66](docs/learning/66-community-and-member-access.md) for setup and the UI/API/storage walkthrough. Community opinions never become RAG evidence.

Accounts use Argon2id password hashes, opaque HTTP-only sessions, CSRF/Origin checks, durable throttling and revision-protected collection writes. Existing-session reads do not rewrite cookies, anonymous bootstrap has a separate cookie, and account switches clear previous personal state. See [Lesson 64](docs/learning/64-personal-accounts.md) for the full UI/API/storage walkthrough and tested failure cases. Public HTTPS deployments must configure the exact `FRAME_APP_ORIGIN` and `FRAME_SECURE_COOKIES=true`; recovery, MFA/OAuth and production load qualification remain future work. The local configuration uses a clearly labelled email verification preview, restricted to loopback HTTP; no email is sent. Public deployment requires SMTP/TLS delivery instead. See [Lesson 65](docs/learning/65-plotspot-verification-and-temporary-saves.md) and `backend/.env.example`.

The movie view places section navigation below the trailer/save actions. It has no return button or draft workspace. Discover in the main navigation returns to the originating discovery query when available; browser Back also preserves navigation history.

Earlier semantic-search code, lessons, preparation scripts and evaluation reports are retained as historical learning material. They are not active search functionality or evidence of the current keyword search quality. `legacy_semantic_catalog_search.py` isolates that earlier implementation; production startup never loads its inference service.

Discovery searches automatically after a 350 ms typing pause; Enter remains an immediate shortcut. Filters persist and new queries reset pagination. Knives Out and The Truman Show each add five source-reviewed filmmaking facts and ten saved story questions, prepared explicitly without model calls. See [learning note 48](docs/learning/48-auto-search-and-movie-coverage.md).

All ten registered discussion films now have saved facts/quiz collections. The four latest films each add five authored, source-reviewed filmmaking facts and ten story questions. Generation qualification remains separate. See [learning note 49](docs/learning/49-ten-film-saved-coverage.md) and [live coverage report](evals/movie-rag/coverage/ten-film-live-publication.json).

Fresh real-film fact evaluation uses revision-pinned excerpts from six movies: 18/18 assistant-authored challenge labels matched, but inspection of seven actual generated facts found citation and judgement gaps. Five drafts passed automated checks; none were published. These are development observations, not production accuracy. See [lesson 50](docs/learning/50-real-film-fact-evaluation.md) and [reports](evals/movie-rag/real-film-facts/README.md).

Background citations now preserve complete sentences through retrieval, quote selection and explicit publication checks, including personal initials and footnotes. Final local generation produced seven complete quotes; semantic wording/context gaps remain under review. [Lesson 51](docs/learning/51-complete-background-citations.md) explains the fix and actual cached RAG checks. No saved content was rewritten.

The Collections UI lives at `/collections`; historical `/collection` links redirect while retaining query/hash. Account access uses a centered form; guest-save import is on Collections.

### Multi-source movie evidence

Optional free DuckDuckGo/Startpage discovery now supplements Wikipedia, reviewed publisher sources and available IMSDb draft context. Full-page identity/purpose checks, immutable provenance, bounded per-source retrieval and independent support for web quiz answers protect the evidence flow. Set `PLOTSPOT_MOVIE_WEB_SEARCH` in the local backend configuration; see [Lesson 71](docs/learning/71-multi-source-movie-rag.md) for setup and [measured development results](evals/movie-rag/multi-source/README.md) for availability and quality limits. The registered boundary now contains twenty reviewed saved banks; wider automatic production coverage is still qualification work.
