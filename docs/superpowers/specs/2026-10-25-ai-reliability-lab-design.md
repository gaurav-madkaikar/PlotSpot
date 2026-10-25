# PlotSpot AI Reliability Lab Design

**Date:** 2026-10-25
**Status:** Design approved; awaiting written-spec review

## Purpose

PlotSpot already produces evaluation reports, durable preparation checkpoints, and sanitized story-RAG traces. These artifacts are useful to a developer, but they are spread across JSON files and SQLite records with different schemas. The AI Reliability Lab will turn that existing evidence into a coherent, read-only view of system quality and recent pipeline behavior.

The first release is a developer-only local tool. It must help explain whether retrieval, generation, verification, and publication controls are working without exposing internal evidence, user content, or controls that can change application state.

## Success criteria

The lab succeeds when a developer can:

1. Open `/lab` in an explicitly enabled development environment.
2. See the status and sample size of the supported search, fact, quiz, discussion, and retrieval evaluations.
3. Distinguish development, held-out, smoke, live, and publication evidence.
4. Inspect recent sanitized preparation and story-RAG runs as ordered stages.
5. Understand degraded, partial, failed, or missing data without the whole page failing.
6. Confirm that the page cannot execute, cancel, approve, publish, delete, or otherwise mutate a pipeline.

## Chosen approach

Use a hybrid read-only lab that combines stored evaluation summaries with recent live pipeline records. A static report viewer would be simpler but would not explain current runs. A full tracing platform would require event storage, streaming, alerting, and operational controls that the project does not need yet.

## Scope

### Included

- A development-only `/lab` frontend route.
- Read-only backend endpoints under `/api/lab`.
- A backend normalization layer for explicitly registered report and run formats.
- Aggregate quality and health summaries.
- Recent sanitized run summaries and a per-run stage timeline.
- Filters for feature and evidence category.
- Plain-language metric definitions and limitations.
- Loading, empty, partial, disabled, and error states.
- Backend contract, safety, and parser tests plus frontend contract and interaction tests.

### Excluded

- Production deployment or authentication roles for the lab.
- User-facing analytics or transparency views.
- Real-time streaming, WebSockets, alerting, or a metrics database.
- Cost estimates or token accounting unless an existing safe record already provides them.
- Raw prompts, user questions, source passages, screenplay text, generated drafts, or model reasoning.
- Buttons that start, retry, cancel, approve, publish, delete, or otherwise alter work.
- A generic file browser or an API parameter that accepts a filesystem path.

## Access boundary

The lab is off by default. The backend is authoritative and enables `/api/lab/*` only when `PLOTSPOT_LAB_ENABLED=true`; otherwise those routes return `404`. The frontend registers `/lab` only during a Vite development build when `VITE_PLOTSPOT_LAB_ENABLED=true`. It does not add the lab to the normal header or footer navigation.

The two flags are intentionally independent. Hiding a frontend route is a convenience, while the backend flag protects the data boundary. Local setup documentation will state that both are required.

This first version does not treat a normal signed-in account as developer authorization. Production access requires a separate future design with a real operator role.

## Architecture

```text
Allowlisted evaluation reports ----\
                                    -> normalizers -> typed snapshots -> /api/lab -> React Query -> /lab
Preparation job records -----------/
Sanitized story-RAG traces --------/
```

### `lab_registry.py`

Defines the only supported artifact families. Each registry entry contains a stable suite identifier, feature, evidence category, repository-relative path, expected schema version or discriminator, parser, and human-readable metric definitions. Paths are constants owned by the application; clients cannot add or override them.

The initial registry covers these representative artifacts rather than every historical experiment:

- `evals/search/report.json`: spelling suggestions and negative-query behavior, separated into development and held-out partitions.
- `evals/movie-rag/content-quality-held-out-v2-structured-v3-ollama.json`: held-out structured-review label agreement, useful acceptance, false acceptance, and false rejection.
- `evals/movie-rag/real-film-facts/precision-final-inspection.json`: inspected real-film fact support and the report's stated limitations.
- `evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json`: quiz evidence recovery, generation, editorial review, and withheld-reason counts.
- `evals/movie-rag/coverage/discussion-retrieval-review.json`: discussion retrieval and abstention behavior on the recorded development cases.
- `evals/grounding/support-relations-v6.json`: discussion support-review decisions, including false acceptance and false rejection counts.
- `evals/movie-rag/multi-source/local-model-smoke-v1.json`: explicitly labelled multi-source development smoke evidence.
- `evals/movie-rag/research/readiness-v5-final.json`: readiness-control replay results and limitations.
- `evals/movie-rag/expanded-20/final-review-audit-v2.json`: twenty-film reviewability and selection-compilation audit.

Each parser accepts only the structure currently present in its registered artifact. Historical reports remain available in the repository but are not discovered or surfaced automatically.

### `lab_normalizers.py`

Contains small parser functions with one responsibility each. A parser validates its registered input and produces the common contracts below. It does not infer missing metrics, compare unrelated denominators, or convert a smoke result into an accuracy claim.

Unknown versions, malformed values, files larger than the configured limit, and missing files produce a bounded warning for that suite. They do not become successful zero-valued metrics.

### `lab_runs.py`

Projects existing preparation records and story-RAG trace files into safe run summaries. Preparation records are read through a dedicated read-only query rather than through mutation-capable job methods. Story-RAG traces are read only from `backend/data/private/story-rag-traces`, with a fixed maximum file count and size.

The projector uses an explicit output-field allowlist. It never serializes a raw record. Safe fields include opaque run ID, movie ID, workflow, state, stage names, timestamps, elapsed duration when available, source counts, retrieval counts, decision counts, degraded state, and bounded error categories. Movie titles may be resolved from existing catalog metadata; absence of a title is harmless.

### `lab_routes.py`

Provides the read-only API and checks the backend feature flag before every response. It depends on the registry and run reader through explicit constructors so tests can use temporary directories and databases.

### Frontend modules

- `lab-contracts.ts`: Zod schemas and inferred TypeScript types.
- `lab-api.ts`: request functions with abort signals and existing API error conventions.
- `pages/lab.tsx`: page-level queries, filters, and state composition.
- Focused presentational components for snapshot cards, pipeline health, evaluation rows, recent runs, the stage timeline, and limitations.

The page uses existing PlotSpot typography, spacing, surfaces, focus treatment, and footer. Lab-specific CSS remains namespaced under a lab page class.

## API contracts

### `GET /api/lab/overview`

Returns:

- `generated_at`
- `status`: `healthy`, `attention`, `partial`, or `no_data`
- aggregate counts for valid suites, passing suites, recent successful runs, and degraded or failed runs
- normalized evaluation suites
- feature-level pipeline health
- warnings and limitations

### `GET /api/lab/runs`

Accepts only bounded, enumerated filters such as workflow and status plus a capped limit. It returns recent safe summaries. It does not accept paths, SQL fragments, dates without bounds, or arbitrary sort expressions.

### `GET /api/lab/runs/{run_id}`

Returns one sanitized run and its ordered stages. Unknown or no-longer-retained IDs return `404`. Invalid IDs fail validation before storage access.

### Common evaluation shape

Each suite has:

- Stable `id`, title, feature, evidence category, and recorded timestamp when present.
- `status`: `pass`, `attention`, `informational`, `error`, or `no_data`.
- Metrics with label, numerator when meaningful, denominator or sample size, display value, direction, and a plain-language definition.
- Source report label without an absolute filesystem path.
- Limitations copied from a bounded, trusted registry description or a validated report field.
- Warnings describing missing, malformed, or unsupported data.

Percentages are never returned without their numerator and denominator when those values exist. A metric whose denominator is unknown is labelled as such rather than presented as a pass rate.

### Common run shape

Each run has:

- Opaque ID, movie ID and optional title.
- Workflow and state.
- Started, updated, and completed timestamps when available.
- Duration when derivable from trusted timestamps.
- Source and retrieval counts.
- Degraded flag and bounded warning categories.
- Ordered stages with name, state, duration when available, safe counts, and a concise message.

## Status derivation

Status is deterministic and never assigned by an LLM.

- A suite is `pass` only when its registered report contains its own recorded passing decision or satisfies a threshold already defined by that evaluation artifact.
- A valid report that records a failed gate is `attention`.
- A valid report without a preregistered pass/fail gate is `informational`; the lab shows its metrics but excludes it from pass-rate denominators.
- An invalid registered report is `error`.
- A missing optional report is `no_data`.
- Overall status is `attention` when any gated suite or recent run requires attention, `partial` when data is missing or unreadable but no gated suite fails, `healthy` when all required gated suites pass and recent runs are healthy, and `no_data` when no registered evidence can be read. Informational reports alone cannot produce `healthy`.

The lab displays development and held-out evidence separately. It does not combine unlike metrics into a synthetic quality score.

## Interface design

The page is left-aligned and uses the existing light PlotSpot visual language. It contains these sections in order:

1. **Header:** “AI Reliability Lab,” a concise explanation, last refresh time, and a “Development only” label.
2. **System snapshot:** evaluation suites passing, held-out cases passing, recent successful runs, and degraded or failed runs. Every rate includes a sample size.
3. **Pipeline health:** Search, Facts, Quiz, and Discuss rows with retrieval, generation, verification, and publication states where relevant.
4. **Evaluation results:** feature and evidence-category filters, normalized metrics, definitions, source label, and limitations.
5. **Recent runs:** movie, workflow, state, duration, source count, and timestamp.
6. **Inline run detail:** an accessible vertical timeline with safe metadata and warnings. Selecting another row replaces the detail; no modal is used.
7. **Limitations:** persistent explanation of dataset categories, sample sizes, and the difference between smoke checks and accuracy evidence.

Status uses text and icons as well as color. Controls have visible focus states and at least 44-pixel targets. The layout collapses to one column without horizontal scrolling. Tables or grids retain accessible labels on narrow screens. Motion is optional and respects reduced-motion preferences.

## Error and partial-data behavior

- One invalid suite cannot prevent other suites or recent runs from loading.
- Suite warnings appear beside the affected suite and in the overview warning count.
- An unavailable run source leaves the evaluation view usable.
- An unavailable evaluation source leaves recent runs usable.
- A fully disabled backend appears as a normal not-found route rather than revealing the feature.
- A network failure uses the existing retryable status pattern.
- Empty states explain whether there are no recorded runs, no reports, or no matches for the current filter.
- API responses and logs avoid absolute paths and raw exception messages.

## Security and privacy

- Only registered files and configured storage roots are read.
- Files are opened after canonical containment checks and size checks.
- Symlinks that resolve outside an approved root are rejected.
- Raw artifacts are validated before projection.
- Output uses field allowlists; recursive “remove known secrets” filtering is insufficient.
- Prompts, questions, passages, screenplay content, evidence quotes, draft text, email addresses, account identifiers, credentials, and model reasoning are excluded.
- Run IDs exposed by the API are validated opaque identifiers and do not reveal paths.
- The feature remains read-only at the HTTP method, service interface, and UI layers.

## Testing strategy

### Backend

- Unit tests for every registered report normalizer using minimal valid fixtures.
- Cases for missing files, oversized files, invalid JSON, unknown versions, invalid denominators, and unexpected fields.
- Containment and symlink escape tests.
- Projection tests proving sensitive fields never appear in serialized output.
- Preparation and story-RAG run ordering, limit, status, and detail tests.
- Endpoint tests for disabled `404`, enabled success, validation failures, partial results, and unknown run IDs.
- A contract snapshot that the frontend fixtures can consume.

### Frontend

- Zod tests for valid, partial, and malformed responses.
- Page tests for loading, healthy, attention, partial, no-data, and network-error states.
- Filter and inline run-selection tests.
- Assertions that sample sizes, dataset categories, and limitations remain visible.
- Keyboard, focus, accessible-name, and status-text checks.
- Responsive checks at narrow mobile, tablet, and desktop widths.

Tests use temporary artifacts and databases. They do not depend on the developer's private traces or make model, TMDB, Wikipedia, or internet calls.

## Learning outcomes

This feature demonstrates the path from raw operational evidence to a safe product surface:

1. Identify useful signals already produced by a system.
2. Preserve the meaning and denominator of each metric.
3. Normalize heterogeneous data behind typed contracts.
4. Separate observability reads from pipeline mutation interfaces.
5. Redact by construction with explicit projections.
6. Render partial and uncertain evidence honestly.
7. Connect FastAPI models, Zod validation, React Query, and accessible UI states.

A concise learning note will explain these decisions after implementation, following the project's existing `docs/learning` sequence.

## Delivery sequence

1. Introduce backend settings, contracts, registry, normalizers, and safe readers.
2. Add development-only API routes and tests.
3. Add frontend contracts and API client.
4. Build the `/lab` page and focused components.
5. Add visual, accessibility, responsive, and partial-data verification.
6. Add local enablement documentation and the learning note.

Each stage remains reviewable and testable without requiring Ollama or external network access.
