from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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
    with pytest.raises(ValidationError, match="Percent metrics require"):
        LabMetric(
            id="hit",
            label="Hit rate",
            value=80.0,
            unit="percent",
            direction="higher",
            definition="Share of labelled cases retrieved.",
        )


def test_run_contract_rejects_raw_sensitive_fields():
    with pytest.raises(ValidationError, match="prompt"):
        LabRunSummary(
            id="story_" + "a" * 32,
            movie_id=603,
            title="The Matrix",
            workflow="story_rag",
            state="completed",
            updated_at=datetime.now(timezone.utc),
            duration_seconds=None,
            source_count=2,
            retrieval_count=4,
            degraded=False,
            warnings=[],
            prompt="private",
        )


def test_metric_rejects_boolean_as_numeric_value():
    with pytest.raises(ValidationError):
        LabMetric(
            id="count",
            label="Cases",
            value=True,
            unit="count",
            direction="neutral",
            definition="Number of evaluated cases.",
        )
