from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from movie_companion.lab_contracts import (
    LabMetric,
    LabOverview,
    LabRunDetail,
    LabRunList,
    LabRunStage,
    LabRunSummary,
    LabSuite,
    LabWarning,
)
from movie_companion.lab_routes import router
from movie_companion.lab_service import LabService
from movie_companion.settings import get_settings


NOW = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)


def suite(identifier, status, *, gated=False, category="audit", feature="readiness"):
    return LabSuite(
        id=identifier,
        title=identifier,
        feature=feature,
        category=category,
        status=status,
        gated=gated,
        recorded_at=NOW,
        metrics=[
            LabMetric(
                id="passed",
                label="Passed",
                value=100.0,
                unit="percent",
                numerator=2,
                denominator=2,
                direction="higher",
                definition="Recorded checks that passed.",
            )
        ],
        source_label="evals/report.json",
        limitations=["Small local evaluation."],
        warnings=[],
    )


def run(state="completed", degraded=False):
    return LabRunSummary(
        id="story_" + "a" * 32,
        movie_id=603,
        title="The Matrix",
        workflow="story_rag",
        state=state,
        updated_at=NOW,
        duration_seconds=None,
        source_count=2,
        retrieval_count=4,
        degraded=degraded,
        warnings=[],
    )


class FakeRuns:
    def __init__(self, records=None, warnings=None):
        self.records = records or []
        self.warnings = warnings or []

    def list(self, workflow, state, limit):
        records = self.records
        if workflow:
            records = [item for item in records if item.workflow == workflow]
        if state:
            records = [item for item in records if item.state == state]
        return records[:limit], self.warnings

    def get(self, run_id):
        if not self.records or self.records[0].id != run_id:
            return None
        return LabRunDetail(
            **self.records[0].model_dump(),
            stages=[
                LabRunStage(
                    name="retrieve",
                    status="completed",
                    count=4,
                    message="Rank scoped evidence.",
                )
            ],
        )


def service_with(suites, records=None, warnings=None):
    return LabService(
        Path("."),
        FakeRuns(records, warnings),
        suite_loader=lambda _: (suites, []),
        clock=lambda: NOW,
    )


def test_overview_status_is_deterministic_and_informational_is_not_healthy():
    information = service_with([suite("info", "informational")]).overview()
    passing = service_with([suite("gate", "pass", gated=True)]).overview()
    partial = service_with(
        [suite("gate", "pass", gated=True)],
        warnings=[
            LabWarning(
                code="missing_source", suite_id=None, message="Run store unavailable."
            )
        ],
    ).overview()
    attention = service_with(
        [suite("gate", "attention", gated=True)], [run("failed")]
    ).overview()

    assert information.status == "partial"
    assert passing.status == "healthy"
    assert partial.status == "partial"
    assert attention.status == "attention"
    assert passing.gated_passed == passing.gated_total == 1


def test_disabled_lab_is_indistinguishable_from_missing(monkeypatch):
    monkeypatch.setenv("PLOTSPOT_LAB_ENABLED", "false")
    get_settings.cache_clear()
    local = FastAPI()
    local.include_router(router)

    with TestClient(local) as client:
        response = client.get("/api/lab/overview")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


@pytest.fixture
def client_with_lab(monkeypatch):
    monkeypatch.setenv("PLOTSPOT_LAB_ENABLED", "true")
    get_settings.cache_clear()
    local = FastAPI()
    local.include_router(router)
    local.state.lab = service_with(
        [suite("gate", "pass", gated=True)], [run()]
    )
    with TestClient(local) as client:
        yield client
    get_settings.cache_clear()


def test_enabled_lab_is_read_only_and_returns_contract(client_with_lab):
    response = client_with_lab.get("/api/lab/overview")

    assert response.status_code == 200
    assert LabOverview.model_validate_json(response.text)
    assert client_with_lab.post("/api/lab/overview").status_code == 405


def test_run_filters_and_details_are_bounded(client_with_lab):
    response = client_with_lab.get("/api/lab/runs?workflow=story_rag&limit=1")

    assert response.status_code == 200
    assert LabRunList.model_validate_json(response.text).items[0].workflow == "story_rag"
    assert client_with_lab.get("/api/lab/runs?limit=51").status_code == 422
    assert client_with_lab.get("/api/lab/runs?workflow=unknown").status_code == 422
    detail = client_with_lab.get("/api/lab/runs/story_" + "a" * 32)
    assert detail.status_code == 200
    assert LabRunDetail.model_validate_json(detail.text).stages[0].name == "retrieve"
    assert client_with_lab.get("/api/lab/runs/story_" + "f" * 32).status_code == 404
    assert client_with_lab.get("/api/lab/runs/not-valid").status_code == 422
