# Movie Companion — approved design

Approved in conversation on 2026-10-07. Local-first, dark cinematic UI, pair implementation, Python plus some web experience. AI/backend engineering portfolio project. Movies only; English interface and model responses, any original-language movie metadata.

Visual direction updated at the user's explicit revamp request on 2026-10-08: editorial cinema programme with warm paper, ink, vermilion, locally bundled Libre Bodoni / Inter, asymmetric illustrated feature, and responsive poster grids. This supersedes the original dark/amber presentation. Product scope and learning workflow remain as approved. See `design-system/movie-companion/MASTER.md` and the editorial-redesign plan.

## Product

Discover movies through titles, cast, typos, and meaning-based requests. Tiles open dedicated movie pages with metadata, external news facts, quizzes, AI discussion, and community threads/replies. Include watchlists, watched status, editable preferences, private notes, and two spoiler modes. Future ratings, television, votes, public deployment, and streaming playback are outside v1.

The semantic starter catalog has 200 films; live title/actor search has broader coverage. Deep demo evidence starts with Inception, Interstellar, Arrival, The Matrix, Knives Out, Parasite, Spirited Away, The Truman Show, The Grand Budapest Hotel, and Dune (2021). Clearly disclose bounded coverage and missing sources.

Facts concern external reporting, production, interviews, releases, festivals, and related news, rather than story trivia. News facts have attribution and dates. Movie interpretations are labeled opinions; claims of filmmaker intent need supporting interviews. Quizzes have objective, sourced, unique correct answers. Public comments are opinions, not trusted factual evidence. AI content never impersonates human consensus.

## Architecture

React/TypeScript/Vite, Tailwind/shadcn components, React Router, TanStack Query; Python 3.12/FastAPI/Pydantic/HTTPX; SQLite/SQLAlchemy/Alembic; persistent local Chroma plus SQLite FTS5; Ollama qwen3:4b and nomic-embed-text:v1.5; LangGraph. One modular backend. No microservices, mandatory paid services, or cloud model inference.

TMDB supplies identity, overview, cast, genres, posters, and discovery with required attribution. Ollama web search discovers external news using bounded requests. Wikimedia supplies attributed/revisioned reusable plot and production passages. IMSDb provides links by default; ingest scripts only when authorized, preserving draft/version identity. Script availability is optional. Public fixtures must not redistribute unauthorized articles or scripts.

Discover and validate canonical catalog IDs; distinguish title matching from actual semantic search. Actor results use cast credits and disambiguation. Source identification checks film title/year and director/cast. Recommendations apply hard constraints before ranking and avoid invented movies.

RAG maintains separate catalog and evidence collections. Evidence records include movie ID, source URL/type, publication/fetch dates, revision, spoiler status, and ownership. Start at 450-token chunks, 80-token overlap, hybrid lexical/vector retrieval, and up to six final passages. Ingest selected films on demand and reuse cached evidence.

## Agents, safety, and memory

News Research and Story Evidence can execute independently; Quiz and Discussion consume approved evidence when requested. The orchestrator owns typed state, routing, budgets, one repair attempt, cancellation, and partial results. Keep ordinary catalog work deterministic. Parallel network work starts immediately; model concurrency starts at one and is benchmarked against two before adoption.

Authorization is backend code outside model prompts. Agents get read-only scoped tools; no shell, arbitrary files, arbitrary URL fetch, automatic posting, or deletion. Fixed provider endpoints, bounded requests/timeouts, input/output schemas, citation validation, owner filters, sanitized community content, and adversarial evals establish testable boundaries. Source material is always untrusted. Passing a suite does not imply universal injection prevention.

Spoiler permission filters evidence before prompting. Unknown classifications are not safe. Story quizzes and detailed story discussions require opt-in. Switching spoiler mode must not reuse incompatible generated output or context. No script timestamps are invented.

Accounts eventually use hashed local username/password credentials, HTTP-only sessions, CSRF protection, and owner checks. Long-term memory stores explicit editable preferences rather than entire conversations. Private data does not enter public retrieval or external web queries. Local service ports bind to loopback.

Developer traces record run state, tool calls, evidence IDs, model/prompt versions, latency, token counts, retries, and failures while excluding secrets and routine raw private content. Missing evidence, quotas, unavailable inference, and interrupted jobs have explicit recoverable states.

## Learning progression

1. Foundation and UI contracts.
2. TMDB, caching, actor entity resolution, and fuzzy search.
3. Embeddings and constrained semantic recommendations.
4. Provenance-aware evidence ingestion.
5. Single-agent grounded RAG and retrieval experiments.
6. Parallel agents, state, recovery, quizzes, and comparisons.
7. Accounts, community, and deliberate memory.
8. Consolidated evaluation, CI, benchmark report, and demo.

Each stage follows explanation → small learner exercise → pair implementation → meaningful verification → recorded tradeoff. Do not autonomously complete all milestones in one pass. Introduce a labeled baseline before each agent and keep regression checks throughout; milestone 8 consolidates evaluation rather than introducing it.

## Evaluation and acceptance

Build 120 labeled scenarios across search, recommendations, retrieval, facts/quizzes, safety/spoilers, and failures, with development and held-out partitions. Initial targets: 90% top-five identity accuracy, 80% Recall@6, 90% supported factual claims, reported answer coverage, and all deterministic permission/isolation checks passing. Compare single-agent and parallel quality, latency, tokens, and resources. Human review assesses interpretations and claim support; an LLM judge is optional evidence, not the sole authority.

CI runs deterministic fixture-backed checks; real Ollama evaluations run locally and publish versioned reports. Demo the typo and semantic searches, cited facts, sourced quiz feedback, spoiler-aware conversation, user-published thread/reply, injection resistance, and partial failure. Label snapshots and sample users. Resume claims must use measured results.

## Source documentation

- https://developer.themoviedb.org/docs/faq
- https://ollama.com/blog/web-search
- https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse
- https://imsdb.com/disclaimer.html
- https://docs.ollama.com/faq
- https://docs.langchain.com/oss/python/langgraph/workflows-agents
- https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
