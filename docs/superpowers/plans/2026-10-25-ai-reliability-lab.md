# PlotSpot AI Reliability Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a development-only, read-only `/lab` that explains PlotSpot's stored AI evaluations and recent sanitized preparation and story-RAG runs.

**Architecture:** FastAPI loads only registered evaluation artifacts and approved local run stores, normalizes them into strict Pydantic contracts, and exposes three guarded GET endpoints. React validates those responses with Zod and renders a light, accessible PlotSpot dashboard with aggregate health, evaluation details, recent runs, and an inline stage timeline.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, pytest, React 19, TypeScript, Zod, TanStack Query, React Router, Lucide, CSS, Playwright.

## Global Constraints

- The backend lab is disabled unless `PLOTSPOT_LAB_ENABLED=true`; disabled endpoints return `404`.
- The frontend route exists only in a Vite development build with `VITE_PLOTSPOT_LAB_ENABLED=true`.
- The lab is absent from the normal header and footer navigation.
- Every endpoint is GET-only and every service interface is read-only.
- Report paths come only from a server-owned registry; no request accepts a file path.
- Raw prompts, user questions, passages, scripts, evidence quotes, draft text, account data, credentials, and model reasoning never enter API responses.
- Percentages retain their numerator and denominator; unlike metrics are never merged into one synthetic quality score.
- Development, held-out, smoke, live, publication, and audit evidence remain visibly distinct.
- Invalid or missing sources degrade one section without breaking the complete page.
- No Ollama, TMDB, Wikipedia, IMSDb, or internet call is allowed in tests.
- Tests use temporary report roots, trace roots, and SQLite databases.
- UI status is expressed with text and icons in addition to color, has visible focus, uses 44-pixel controls, and does not scroll horizontally at 375 pixels.
- No real-time streaming, metrics database, alerting, mutation controls, or production operator role is added.

## File map

### Backend

- `backend/src/movie_companion/settings.py`: parse the backend feature flag.
- `backend/src/movie_companion/lab_contracts.py`: strict public API models shared by the lab services and routes.
- `backend/src/movie_companion/lab_registry.py`: fixed report registry and bounded file loading.
- `backend/src/movie_companion/lab_normalizers.py`: artifact-specific parsers that preserve each report's meaning.
- `backend/src/movie_companion/lab_runs.py`: safe read-only projection of preparation rows and story-RAG trace files.
- `backend/src/movie_companion/lab_service.py`: aggregate suites and runs into overview and pipeline health.
- `backend/src/movie_companion/lab_routes.py`: guarded GET endpoints.
- `backend/src/movie_companion/main.py`: create the enabled service and include its router.
- `backend/tests/test_lab_contracts.py`: flag and strict-contract checks.
- `backend/tests/test_lab_normalizers.py`: registered report parsing and partial-data checks.
- `backend/tests/test_lab_runs.py`: SQLite/trace projection, limits, containment, and redaction.
- `backend/tests/test_lab_routes.py`: HTTP gate, filters, response contracts, and unknown IDs.

### Frontend

- `frontend/src/lib/lab-contracts.ts`: Zod schemas and inferred types.
- `frontend/src/lib/lab-api.ts`: abortable GET client for the lab.
- `frontend/src/pages/lab.tsx`: query and selection state for the lab page.
- `frontend/src/components/lab-summary.tsx`: overview cards and pipeline health.
- `frontend/src/components/lab-evaluations.tsx`: filters, suite metrics, definitions, warnings, and limitations.
- `frontend/src/components/lab-runs.tsx`: recent-run list and accessible inline timeline.
- `frontend/src/main.tsx`: conditional lazy `/lab` route.
- `frontend/src/styles.css`: namespaced responsive lab styles.
- `frontend/playwright.config.ts`: explicitly enable the frontend lab route in browser tests.
- `frontend/e2e/lab.spec.ts`: mocked healthy, partial, interaction, accessibility, and mobile flows.

### Documentation

- `backend/.env.example`: backend enablement flag.
- `frontend/.env.example`: frontend development flag.
- `README.md`: local lab startup and safety boundary.
- `docs/learning/82-ai-reliability-lab.md`: learning walkthrough.
- `docs/learning/PROGRESS.md`: delivered checkpoint.
- `docs/PROJECT_CHECKLIST.md`: evaluation/portfolio status.

---

### Task 1: Feature flag and strict lab contracts

**Files:**
- Modify: `backend/src/movie_companion/settings.py:10-22`
- Create: `backend/src/movie_companion/lab_contracts.py`
- Create: `backend/tests/test_lab_contracts.py`

**Interfaces:**
- Produces: `Settings.lab_enabled: bool`.
- Produces: `LabMetric`, `LabWarning`, `LabSuite`, `PipelineStageHealth`, `FeatureHealth`, `LabOverview`, `LabRunStage`, `LabRunSummary`, `LabRunDetail`, and `LabRunList`.
- Consumes: `StrictRecord` from `movie_companion.content_proposals` so unknown response fields are rejected.

- [ ] **Step 1: Write failing flag and contract tests**

```python
from pydantic import ValidationError
import pytest

from movie_companion.lab_contracts import LabMetric, LabRunSummary
from movie_companion.settings import get_settings


def test_lab_flag_is_false_by_default_and_accepts_exact_true(monkeypatch):
    monkeypatch.delenv("PLOTSPOT_LAB_ENABLED", raising=False)
    get_settings.cache_clear()
    assert get_settings().lab_enabled is False
    monkeypatch.setenv("PLOTSPOT_LAB_ENABLED", "true")
    get_settings.cache_clear()
    assert get_settings().lab_enabled is True


def test_invalid_lab_flag_fails_closed(monkeypatch):
    monkeypatch.setenv("PLOTSPOT_LAB_ENABLED", "1")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="true or false"):
        get_settings()


def test_metric_requires_denominator_for_percentage():
    with pytest.raises(ValidationError):
        LabMetric(id="hit", label="Hit rate", value=80, unit="percent")


def test_run_contract_rejects_raw_sensitive_fields():
    with pytest.raises(ValidationError):
        LabRunSummary(
            id="story_" + "a" * 32,
            movie_id=603,
            title="The Matrix",
            workflow="story_rag",
            state="completed",
            updated_at="2026-10-25T10:00:00Z",
            duration_seconds=None,
            source_count=2,
            retrieval_count=4,
            degraded=False,
            warnings=[],
            prompt="private",
        )
```

- [ ] **Step 2: Run the focused test and confirm it fails because the module and flag do not exist**

Run: `cd backend && uv run pytest tests/test_lab_contracts.py -q`

Expected: collection fails for missing `movie_companion.lab_contracts`.

- [ ] **Step 3: Add exact boolean parsing to settings**

```python
def _flag(name: str) -> bool:
    value = os.getenv(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false")
    return value == "true"


class Settings(BaseModel):
    data_source: Literal["demo", "tmdb"] = "demo"
    tmdb_read_token: str = Field(default="", repr=False, exclude=True)
    lab_enabled: bool = False
```

Pass `lab_enabled=_flag("PLOTSPOT_LAB_ENABLED")` from `get_settings()`.

- [ ] **Step 4: Define strict API contracts**

```python
EvidenceCategory = Literal["development", "held_out", "smoke", "live", "publication", "audit"]
SuiteStatus = Literal["pass", "attention", "informational", "error", "no_data"]
RunState = Literal[
    "queued", "running", "completed", "needs_review", "incomplete", "ready",
    "published", "failed", "cancelled", "interrupted",
]


class LabMetric(StrictRecord):
    id: str = Field(pattern=r"^[a-z0-9_]{1,50}$")
    label: str = Field(min_length=1, max_length=100)
    value: int | float | str
    unit: Literal["count", "percent", "seconds", "ratio", "text"]
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=1)
    direction: Literal["higher", "lower", "neutral"] = "neutral"
    definition: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def percentage_has_fraction(self):
        if self.unit == "percent" and (self.numerator is None or self.denominator is None):
            raise ValueError("Percent metrics require numerator and denominator")
        return self


class LabWarning(StrictRecord):
    code: Literal["missing_source", "invalid_source", "unsupported_source"]
    suite_id: str | None = Field(default=None, max_length=60)
    message: str = Field(min_length=1, max_length=240)


class LabSuite(StrictRecord):
    id: str = Field(pattern=r"^[a-z0-9_]{1,60}$")
    title: str = Field(min_length=1, max_length=120)
    feature: Literal["search", "facts", "quiz", "discuss", "retrieval", "readiness"]
    category: EvidenceCategory
    status: SuiteStatus
    gated: bool
    recorded_at: datetime | None = None
    metrics: list[LabMetric] = Field(max_length=30)
    source_label: str = Field(min_length=1, max_length=160)
    limitations: list[str] = Field(max_length=12)
    warnings: list[LabWarning] = Field(max_length=12)


class PipelineStageHealth(StrictRecord):
    stage: Literal["retrieval", "generation", "verification", "publication"]
    status: Literal["healthy", "attention", "no_data", "not_applicable"]
    detail: str = Field(min_length=1, max_length=180)


class FeatureHealth(StrictRecord):
    feature: Literal["search", "facts", "quiz", "discuss"]
    status: Literal["healthy", "attention", "partial", "no_data"]
    stages: list[PipelineStageHealth] = Field(min_length=1, max_length=4)


class LabOverview(StrictRecord):
    generated_at: datetime
    status: Literal["healthy", "attention", "partial", "no_data"]
    gated_passed: int = Field(ge=0)
    gated_total: int = Field(ge=0)
    held_out_passed: int = Field(ge=0)
    held_out_total: int = Field(ge=0)
    recent_successful_runs: int = Field(ge=0)
    degraded_or_failed_runs: int = Field(ge=0)
    suites: list[LabSuite] = Field(max_length=20)
    features: list[FeatureHealth] = Field(max_length=4)
    warnings: list[LabWarning] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)


class LabRunStage(StrictRecord):
    name: Literal["source", "index", "retrieve", "retrieving", "generate", "generating", "verify", "reviewing", "finished"]
    status: Literal["completed", "running", "attention", "pending", "unavailable"]
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    count: int | None = Field(default=None, ge=0)
    message: str = Field(min_length=1, max_length=180)


class LabRunSummary(StrictRecord):
    id: str = Field(pattern=r"^(?:prep|story)_[a-f0-9]{32}$")
    movie_id: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=200)
    workflow: Literal["preparation", "story_rag"]
    state: RunState
    updated_at: datetime
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    source_count: int = Field(ge=0)
    retrieval_count: int = Field(ge=0)
    degraded: bool
    warnings: list[LabWarning] = Field(max_length=10)


class LabRunDetail(LabRunSummary):
    stages: list[LabRunStage] = Field(min_length=1, max_length=12)


class LabRunList(StrictRecord):
    items: list[LabRunSummary] = Field(max_length=50)
    warnings: list[LabWarning] = Field(max_length=20)
```

Import `datetime`, `model_validator`, and the required Pydantic field types. Configure `StrictRecord` inheritance so unknown fields remain rejected. Use strict integer/finite-float types for `LabMetric.value` so JSON booleans cannot pass as numeric metrics.

- [ ] **Step 5: Run the focused tests**

Run: `cd backend && uv run pytest tests/test_lab_contracts.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the contracts**

```bash
git add backend/src/movie_companion/settings.py backend/src/movie_companion/lab_contracts.py backend/tests/test_lab_contracts.py
git commit -m "feat: define reliability lab contracts"
```

---

### Task 2: Registered evaluation loading and normalization

**Files:**
- Create: `backend/src/movie_companion/lab_registry.py`
- Create: `backend/src/movie_companion/lab_normalizers.py`
- Create: `backend/tests/test_lab_normalizers.py`

**Interfaces:**
- Consumes: `LabSuite`, `LabMetric`, and `LabWarning` from Task 1.
- Produces: `SuiteDefinition(id, feature, category, relative_path, parser, required)`.
- Produces: `registered_suites() -> tuple[SuiteDefinition, ...]`.
- Produces: `load_evaluation_suites(project_root: Path, definitions: Sequence[SuiteDefinition] | None = None, max_bytes: int = 2_000_000) -> tuple[list[LabSuite], list[LabWarning]]`.
- Produces artifact parsers named `parse_search`, `parse_content_quality`, `parse_fact_inspection`, `parse_quiz_completion`, `parse_discussion_retrieval`, `parse_discussion_support`, `parse_multi_source_smoke`, `parse_readiness`, and `parse_twenty_film_audit`.

- [ ] **Step 1: Write failing loader tests with temporary artifacts**

```python
def test_loader_contains_paths_and_keeps_one_bad_suite_partial(tmp_path):
    good = tmp_path / "evals/good.json"
    bad = tmp_path / "evals/bad.json"
    good.parent.mkdir()
    good.write_text('{"summary":{"passed":2,"total":2}}')
    bad.write_text("not json")
    definitions = (
        definition("good", "quiz", "audit", "evals/good.json", parse_readiness),
        definition("bad", "facts", "development", "evals/bad.json", parse_fact_inspection),
    )
    suites, warnings = load_evaluation_suites(tmp_path, definitions)
    assert [suite.id for suite in suites] == ["good", "bad"]
    assert suites[0].status == "pass"
    assert suites[1].status == "error"
    assert warnings[0].suite_id == "bad"
    assert str(tmp_path) not in warnings[0].message


def test_loader_rejects_symlink_escape_and_oversized_file(tmp_path):
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}")
    root = tmp_path / "project"
    root.mkdir()
    (root / "escape.json").symlink_to(outside)
    suites, warnings = load_evaluation_suites(
        root,
        (definition("escape", "search", "audit", "escape.json", parse_search),),
        max_bytes=32,
    )
    assert suites[0].status == "error"
    assert warnings[0].code == "invalid_source"
```

Add an integration test that calls `load_evaluation_suites(PROJECT_ROOT)` and asserts all nine registered IDs are returned, none has status `error`, and every percentage metric has a denominator.

- [ ] **Step 2: Run the focused test and confirm missing registry modules**

Run: `cd backend && uv run pytest tests/test_lab_normalizers.py -q`

Expected: collection fails for missing lab registry and normalizers.

- [ ] **Step 3: Implement fixed definitions and bounded loading**

```python
@dataclass(frozen=True)
class SuiteDefinition:
    id: str
    feature: Literal["search", "facts", "quiz", "discuss", "retrieval", "readiness"]
    category: EvidenceCategory
    relative_path: str
    parser: Callable[[dict[str, Any], "SuiteDefinition"], LabSuite]
    required: bool = False


def _safe_file(project_root: Path, relative_path: str, max_bytes: int) -> Path:
    root = project_root.resolve()
    candidate = root.joinpath(relative_path)
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or candidate.is_symlink():
        raise ValueError("invalid_source")
    if not resolved.is_file() or resolved.stat().st_size > max_bytes:
        raise ValueError("invalid_source")
    return resolved
```

Register only the nine exact artifact paths listed in the approved design. Do not use glob discovery. Convert missing, invalid, oversized, or schema-mismatched input into an error/no-data `LabSuite` plus a bounded warning; never include the exception or absolute path.

- [ ] **Step 4: Implement artifact-specific parsers**

Use helper constructors for count, duration, and percentage metrics, but keep each artifact parser explicit. The mapping must preserve these meanings:

- Search: separate development and held-out suggestion hit counts and false suggestions; informational because the report defines no adoption gate.
- Held-out content quality: label matches, useful acceptance, false acceptance, false rejection, uncertainty, and errors; informational because the report records measurements without a pass decision.
- Fact inspection: supported inspected count, inspected total, generation seconds, and publication-performed flag; informational.
- Quiz completion: evidence recovery, deterministic/critic/editorial funnel, withheld reasons, and recorded model seconds; informational because `proposal_only` is not publication success.
- Discussion retrieval: candidate versus baseline pass counts, support-hit counts, expected abstentions, errors, and median seconds; informational.
- Discussion support: recorded pass, false-acceptance, and false-rejection counts; informational unless the artifact itself contains a gate result.
- Multi-source smoke: checks and case counts with the report's smoke-only scope; informational.
- Readiness: `summary.passed / summary.total`; pass only when equal and the control report is structurally complete.
- Twenty-film audit: movie count, reviewability, and selection compilation; pass only when both booleans are true.

Every parser copies only bounded, validated limitations and registry-owned definitions. It must reject booleans used as integers and non-finite numeric values.

- [ ] **Step 5: Run focused and real-artifact tests**

Run: `cd backend && uv run pytest tests/test_lab_normalizers.py -q`

Expected: all tests pass; registered artifacts parse without model or network access.

- [ ] **Step 6: Commit evaluation normalization**

```bash
git add backend/src/movie_companion/lab_registry.py backend/src/movie_companion/lab_normalizers.py backend/tests/test_lab_normalizers.py
git commit -m "feat: normalize reliability evaluations"
```

---

### Task 3: Safe recent-run projection

**Files:**
- Create: `backend/src/movie_companion/lab_runs.py`
- Create: `backend/tests/test_lab_runs.py`

**Interfaces:**
- Consumes: `LabRunSummary`, `LabRunDetail`, `LabRunStage`, and `LabWarning` from Task 1.
- Produces: `LabRunReader(preparation_db: Path, trace_root: Path, title_lookup: Callable[[int], str | None] | None = None)`.
- Produces: `LabRunReader.list(workflow: Literal["preparation", "story_rag"] | None, state: str | None, limit: int) -> tuple[list[LabRunSummary], list[LabWarning]]`.
- Produces: `LabRunReader.get(run_id: str) -> LabRunDetail | None`.

- [ ] **Step 1: Write failing SQLite, trace, and redaction tests**

Create a temporary `jobs` table with one validated payload containing deliberately sensitive `question`, `evidence_quote`, `text`, `email`, and `prompt` fields. Create one story trace containing safe counts plus deliberately sensitive hit content.

```python
reader = LabRunReader(db_path, trace_root, lambda movie_id: {603: "The Matrix"}.get(movie_id))
runs, warnings = reader.list(workflow=None, state=None, limit=10)
assert [run.id.split("_")[0] for run in runs] == ["story", "prep"]
assert warnings == []
encoded = json.dumps([run.model_dump() for run in runs])
for secret in ["private question", "evidence quote", "user@example.com", "raw prompt"]:
    assert secret not in encoded
detail = reader.get(runs[0].id)
assert detail is not None
assert [stage.name for stage in detail.stages]
assert "script_hits" not in detail.model_dump_json()
```

Add cases for missing stores, malformed rows, oversized traces, trace symlinks, limits above 50, invalid run IDs, stable newest-first ordering, and `get()` returning `None` for an unknown valid ID.

- [ ] **Step 2: Run the focused test and confirm the reader is missing**

Run: `cd backend && uv run pytest tests/test_lab_runs.py -q`

Expected: collection fails for missing `movie_companion.lab_runs`.

- [ ] **Step 3: Implement read-only preparation access**

Open SQLite with `sqlite3.connect(f"file:{quoted_path}?mode=ro", uri=True)`. Read at most 50 rows ordered by sequence descending. Validate row identity against the decoded payload, then project only:

```python
{
    "id": f"prep_{record['id']}",
    "movie_id": record["movie_id"],
    "workflow": "preparation",
    "state": normalized_state(record["state"]),
    "updated_at": validated_timestamp(record.get("updated_at")),
    "source_count": bounded_count(report, "sources"),
    "retrieval_count": bounded_retrieval_count(report),
    "degraded": bounded_degraded(report),
}
```

Build the stage timeline from the known sequence `source`, `retrieving`, `generating`, `reviewing`, `finished`. A stage is completed only when the stored phase/state proves it. Messages come from a code-owned mapping, not raw payload text.

- [ ] **Step 4: Implement bounded story-trace access**

Read only direct `*.json` children whose names match `^(?P<movie>[1-9][0-9]*)-(?P<id>[a-f0-9]{32})\.json$`. Reject symlinks, files over 1 MB, and resolved paths outside `trace_root`. Sort by file modification time and cap inspection at the newest 50.

Project safe counts from `index`, `wiki_hits`, `script_hits`, `decisions`, `candidate_count`, `repair_attempted`, and `mode`. Use stages `index`, `retrieve`, `generate`, and `verify`. Use file modification time as `updated_at`, label duration unavailable, and expose the ID as `story_<hex>`.

- [ ] **Step 5: Run focused tests**

Run: `cd backend && uv run pytest tests/test_lab_runs.py -q`

Expected: all tests pass and serialized contracts contain none of the seeded sensitive values.

- [ ] **Step 6: Commit safe run projection**

```bash
git add backend/src/movie_companion/lab_runs.py backend/tests/test_lab_runs.py
git commit -m "feat: project safe reliability runs"
```

---

### Task 4: Aggregate service and guarded API

**Files:**
- Create: `backend/src/movie_companion/lab_service.py`
- Create: `backend/src/movie_companion/lab_routes.py`
- Modify: `backend/src/movie_companion/main.py:20-43,87-112`
- Create: `backend/tests/test_lab_routes.py`

**Interfaces:**
- Consumes: `load_evaluation_suites()` from Task 2 and `LabRunReader` from Task 3.
- Produces: `LabService(project_root: Path, runs: LabRunReader)` with `overview()`, `list_runs()`, and `get_run()`.
- Produces: `get_lab_service(request: Request) -> LabService` FastAPI dependency.
- Produces: GET `/api/lab/overview`, GET `/api/lab/runs`, and GET `/api/lab/runs/{run_id}`.

- [ ] **Step 1: Write failing service and route tests**

```python
def test_disabled_lab_is_indistinguishable_from_missing(monkeypatch):
    monkeypatch.setenv("PLOTSPOT_LAB_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.get("/api/lab/overview").status_code == 404


def test_enabled_lab_is_read_only_and_returns_contract(client_with_lab):
    response = client_with_lab.get("/api/lab/overview")
    assert response.status_code == 200
    assert LabOverview.model_validate(response.json())
    assert client_with_lab.post("/api/lab/overview").status_code == 405


def test_run_filters_are_bounded(client_with_lab):
    assert client_with_lab.get("/api/lab/runs?limit=51").status_code == 422
    assert client_with_lab.get("/api/lab/runs?workflow=unknown").status_code == 422
    assert client_with_lab.get("/api/lab/runs/story_" + "f" * 32).status_code == 404
```

The enabled fixture uses temporary evals, traces, and SQLite, then injects a `LabService` through `app.dependency_overrides[get_lab_service]`. Add a service test proving one failed suite produces `partial`, a failed gated suite produces `attention`, informational-only data cannot produce `healthy`, and warnings contain no absolute path.

- [ ] **Step 2: Run the route tests and confirm missing modules**

Run: `cd backend && uv run pytest tests/test_lab_routes.py -q`

Expected: collection fails for missing service/routes.

- [ ] **Step 3: Implement deterministic aggregation**

```python
class LabService:
    def overview(self) -> LabOverview:
        suites, suite_warnings = load_evaluation_suites(self.project_root)
        runs, run_warnings = self.runs.list(None, None, 20)
        return build_overview(suites, runs, suite_warnings + run_warnings)

    def list_runs(self, workflow, state, limit) -> LabRunList:
        items, warnings = self.runs.list(workflow, state, limit)
        return LabRunList(items=items, warnings=warnings)

    def get_run(self, run_id) -> LabRunDetail | None:
        return self.runs.get(run_id)
```

`build_overview()` groups suites by feature without averaging their values. Gated pass counts exclude informational suites. Feature health uses code-owned stage applicability: Search has retrieval; Facts and Quiz have retrieval/generation/verification/publication; Discuss has retrieval/generation/verification. Missing inapplicable stages are labelled `not_applicable`, not failed.

- [ ] **Step 4: Implement GET-only routes and backend gate**

Use `Annotated` path/query constraints. Run filesystem and SQLite reads with `asyncio.to_thread`. `get_lab_service()` checks `get_settings().lab_enabled` before reading `request.app.state.lab`; both disabled and absent service return `HTTPException(404)` with `Not found`.

Include `lab_router` unconditionally so disabled paths consistently return route-level `404`. During lifespan, create `app.state.lab` only when enabled, using:

- project root `Path(__file__).resolve().parents[3]`
- preparation DB `app.state.preparation.store.path`
- story trace root `app.state.questions.story.trace_root`
- a bounded catalog title lookup that returns `None` on failure

- [ ] **Step 5: Run backend lab and regression tests**

Run: `cd backend && uv run pytest tests/test_lab_contracts.py tests/test_lab_normalizers.py tests/test_lab_runs.py tests/test_lab_routes.py tests/test_request_logging.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the API**

```bash
git add backend/src/movie_companion/lab_service.py backend/src/movie_companion/lab_routes.py backend/src/movie_companion/main.py backend/tests/test_lab_routes.py
git commit -m "feat: expose guarded reliability lab API"
```

---

### Task 5: Frontend contracts, client, and hidden development route

**Files:**
- Create: `frontend/src/lib/lab-contracts.ts`
- Create: `frontend/src/lib/lab-api.ts`
- Modify: `frontend/src/main.tsx:41-76`
- Modify: `frontend/playwright.config.ts:24-36`

**Interfaces:**
- Consumes the exact JSON shapes from Task 1.
- Produces: `labOverviewSchema`, `labRunListSchema`, `labRunDetailSchema` and inferred `LabOverview`, `LabRunSummary`, `LabRunDetail`.
- Produces: `getLabOverview(signal?)`, `getLabRuns(filters, signal?)`, and `getLabRun(id, signal?)`.
- Produces: conditional lazy route `/lab`.

- [ ] **Step 1: Define Zod schemas that mirror every backend bound**

```typescript
const warningSchema = z.object({
  code: z.enum(['missing_source', 'invalid_source', 'unsupported_source']),
  suite_id: z.string().max(60).nullable(),
  message: z.string().min(1).max(240),
})

export const metricSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9_]{1,50}$/),
    label: z.string().min(1).max(100),
    value: z.union([z.number().finite(), z.string().max(100)]),
    unit: z.enum(['count', 'percent', 'seconds', 'ratio', 'text']),
    numerator: z.number().int().nonnegative().nullable(),
    denominator: z.number().int().positive().nullable(),
    direction: z.enum(['higher', 'lower', 'neutral']),
    definition: z.string().min(1).max(300),
  })
  .superRefine((metric, context) => {
    if (
      metric.unit === 'percent' &&
      (metric.numerator === null || metric.denominator === null)
    )
      context.addIssue({ code: 'custom', message: 'Percent requires fraction' })
  })
```

Mirror all suite, pipeline, overview, run summary, stage, detail, and list literals and maximum list lengths from Pydantic. Do not use `.passthrough()`.

- [ ] **Step 2: Implement the abortable read-only client**

```typescript
async function labRequest<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal) {
  const response = await fetch(path, {
    method: 'GET',
    cache: 'no-store',
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) throw new LabApiError(response.status)
  return schema.parse(await response.json())
}
```

Construct run-list query parameters from the enumerated workflow/state types and an integer limit. Construct the detail path only after the ID passes `/^(?:prep|story)_[a-f0-9]{32}$/`.

- [ ] **Step 3: Register `/lab` only under the explicit frontend development flag**

```typescript
const labEnabled =
  import.meta.env.DEV &&
  import.meta.env.VITE_PLOTSPOT_LAB_ENABLED === 'true'

// Inside route children, before the wildcard:
...(labEnabled
  ? [
      {
        path: '/lab',
        lazy: async () => ({
          Component: (await import('./pages/lab')).LabPage,
        }),
      },
    ]
  : []),
```

Do not edit `shell.tsx`; the lab must not appear in consumer navigation. Set `VITE_PLOTSPOT_LAB_ENABLED: 'true'` only in the Playwright frontend web-server environment.

- [ ] **Step 4: Add a temporary minimal page export and run the build**

Create `frontend/src/pages/lab.tsx` with an accessible `<h1>AI Reliability Lab</h1>` and no data calls yet, so the lazy import compiles independently.

Run: `cd frontend && npm run build`

Expected: TypeScript and Vite build pass.

- [ ] **Step 5: Commit the frontend boundary**

```bash
git add frontend/src/lib/lab-contracts.ts frontend/src/lib/lab-api.ts frontend/src/pages/lab.tsx frontend/src/main.tsx frontend/playwright.config.ts
git commit -m "feat: add reliability lab frontend boundary"
```

---

### Task 6: Accessible reliability lab interface

**Files:**
- Modify: `frontend/src/pages/lab.tsx`
- Create: `frontend/src/components/lab-summary.tsx`
- Create: `frontend/src/components/lab-evaluations.tsx`
- Create: `frontend/src/components/lab-runs.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/e2e/lab.spec.ts`

**Interfaces:**
- Consumes: `getLabOverview`, `getLabRuns`, `getLabRun` and their inferred types from Task 5.
- Produces: a read-only `/lab` page with local feature/category filters and one selected run ID.
- Produces accessible components `LabSummary`, `LabEvaluations`, and `LabRuns`.

- [ ] **Step 1: Write failing browser tests with fixed API fixtures**

Mock all three `/api/lab` endpoints before visiting `/lab`. The fixture must include one passing audit, one informational held-out suite, one warning, two runs, and a four-stage detail.

```typescript
test('lab explains metrics and opens an inline run timeline', async ({ page }) => {
  await installLabRoutes(page)
  await page.goto('/lab')
  await expect(page.getByRole('heading', { name: 'AI Reliability Lab' })).toBeVisible()
  await expect(page.getByText('2 of 2 gated suites passing')).toBeVisible()
  await expect(page.getByText('Held-out')).toBeVisible()
  await page.getByRole('button', { name: /Inception.*story RAG/i }).click()
  await expect(page.getByRole('heading', { name: 'Run timeline' })).toBeVisible()
  await expect(page.getByText('Retrieve')).toBeVisible()
  await expect(page.getByText('private question')).toHaveCount(0)
})

test('lab keeps partial data usable and has no mutation controls', async ({ page }) => {
  await installLabRoutes(page, { partial: true })
  await page.goto('/lab')
  await expect(page.getByText('Some evidence is unavailable')).toBeVisible()
  await expect(page.getByRole('button', { name: /publish|delete|retry run|cancel/i })).toHaveCount(0)
})

test('lab fits a narrow viewport and supports keyboard run selection', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installLabRoutes(page)
  await page.goto('/lab')
  await page.getByRole('button', { name: /Inception.*story RAG/i }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Run timeline' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
```

- [ ] **Step 2: Run the lab browser test and confirm it fails on the minimal page**

Run: `cd frontend && npm run test:e2e -- lab.spec.ts`

Expected: assertions for snapshot, filters, and runs fail.

- [ ] **Step 3: Implement page queries and state**

Use three React Query keys:

```typescript
const overview = useQuery({
  queryKey: ['lab', 'overview'],
  queryFn: ({ signal }) => getLabOverview(signal),
  staleTime: 30_000,
})
const runs = useQuery({
  queryKey: ['lab', 'runs', workflow, runState],
  queryFn: ({ signal }) => getLabRuns({ workflow, state: runState, limit: 20 }, signal),
  staleTime: 15_000,
})
const detail = useQuery({
  queryKey: ['lab', 'run', selectedRunId],
  queryFn: ({ signal }) => getLabRun(selectedRunId!, signal),
  enabled: selectedRunId !== null,
})
```

Render the page header, “Development only” label, generated time, retryable error state, summary, evaluations, recent runs, and persistent limitations. Filters remain local state and do not modify the URL because the route is an internal tool.

- [ ] **Step 4: Implement focused components**

- `LabSummary` renders four sample-aware snapshot cards and a semantic list of Search, Facts, Quiz, and Discuss stages.
- `LabEvaluations` renders labelled `<select>` controls for feature and evidence category, suite status text, metric values, numerator/denominator, definitions, warnings, and limitations. It never renders a bare percent.
- `LabRuns` renders runs as full-width `<button>` rows with `aria-expanded` and `aria-controls`; the selected detail follows the list in document flow. The timeline is an ordered list with stage state text, duration when available, safe counts, and warnings.
- Use Lucide icons with `aria-hidden="true"`; do not use emoji or icon-only labels.

- [ ] **Step 5: Add namespaced responsive styling**

Add styles under `.lab-page`, `.lab-summary`, `.lab-health`, `.lab-evaluations`, and `.lab-runs`. Reuse existing color variables and typography. Use light paper surfaces, subtle borders, 12–18 pixel corner radii, a maximum two-column desktop grid, one column below 800 pixels, `min-width: 0`, and wrapping metric content. Status dots are decorative; adjacent text carries the status. Add `:focus-visible` treatment and `@media (prefers-reduced-motion: reduce)` compatibility.

- [ ] **Step 6: Run browser tests and build**

Run: `cd frontend && npm run test:e2e -- lab.spec.ts && npm run build`

Expected: lab tests and build pass.

- [ ] **Step 7: Commit the interface**

```bash
git add frontend/src/pages/lab.tsx frontend/src/components/lab-summary.tsx frontend/src/components/lab-evaluations.tsx frontend/src/components/lab-runs.tsx frontend/src/styles.css frontend/e2e/lab.spec.ts
git commit -m "feat: build AI reliability lab interface"
```

---

### Task 7: Enablement documentation, learning note, and complete verification

**Files:**
- Modify: `backend/.env.example:1-31`
- Create: `frontend/.env.example`
- Modify: `README.md`
- Create: `docs/learning/82-ai-reliability-lab.md`
- Modify: `docs/learning/PROGRESS.md`
- Modify: `docs/PROJECT_CHECKLIST.md:18-29`

**Interfaces:**
- Documents the two independent flags and the backend's authoritative gate.
- Explains report normalization, denominators, evidence categories, explicit projection, and partial-data behavior.
- Records measured verification without describing test counts as semantic model accuracy.

- [ ] **Step 1: Document explicit local enablement**

Add to `backend/.env.example`:

```dotenv
# Local developer-only AI Reliability Lab. The backend gate is authoritative.
PLOTSPOT_LAB_ENABLED=false
```

Create `frontend/.env.example`:

```dotenv
# Exposes /lab only in a Vite development build. The backend must also be enabled.
VITE_PLOTSPOT_LAB_ENABLED=false
```

Add a README subsection with exact startup steps: set both flags to `true`, restart both processes, then open `http://127.0.0.1:5173/lab`. State that the route is local, read-only, absent from consumer navigation, and intentionally unavailable in production builds.

- [ ] **Step 2: Write Lesson 82**

Explain, with small examples:

1. Why a report registry is safer than accepting paths.
2. Why `8/10` is more honest than an isolated `80%`.
3. Why development, held-out, and smoke evidence cannot be merged.
4. How an explicit projection prevents prompt/source leakage.
5. How FastAPI/Pydantic becomes JSON, Zod validates it, and React Query owns cache/loading/error state.
6. Why partial data is a valid operational state.

End with “Concepts to explain afterwards” and written answers, matching the learning-document pattern already used in the repository.

- [ ] **Step 3: Update project progress and checklist**

Record the developer-only lab under evaluation/portfolio delivery. State which reports are displayed, that run history is bounded and not a complete event store, and that the dashboard does not establish production model accuracy or provide production monitoring.

- [ ] **Step 4: Run backend verification**

Run: `cd backend && uv run pytest`

Expected: the complete backend suite passes with network and model access disabled by fixtures.

- [ ] **Step 5: Run frontend verification**

Run: `cd frontend && npm run build && npm run test:e2e`

Expected: TypeScript/Vite build and the complete Chromium suite pass.

- [ ] **Step 6: Run repository hygiene checks**

Run:

```bash
git diff --check
git status --short
git log -1 --format='%an <%ae> | %cn <%ce>'
```

Expected: no whitespace errors, only intended files changed before the final commit, and author/committer are `Gaurav Madkaikar <gmadkaikar@gmail.com>`.

- [ ] **Step 7: Commit documentation and verification record**

```bash
git add backend/.env.example frontend/.env.example README.md docs/learning/82-ai-reliability-lab.md docs/learning/PROGRESS.md docs/PROJECT_CHECKLIST.md
git commit -m "docs: explain the AI reliability lab"
```

- [ ] **Step 8: Verify the final branch state**

Run: `git status --short && git log --oneline --decorate -8`

Expected: clean working tree with focused reliability-lab commits on `feature/plotspot-initial-import`; `main` remains unchanged.
