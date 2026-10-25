from pathlib import Path

from movie_companion.lab_normalizers import parse_fact_inspection, parse_readiness
from movie_companion.lab_registry import (
    SuiteDefinition,
    load_evaluation_suites,
    registered_suites,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def definition(identifier, feature, category, relative_path, parser, *, required=False):
    return SuiteDefinition(
        id=identifier,
        title=identifier.replace("_", " ").title(),
        feature=feature,
        category=category,
        relative_path=relative_path,
        parser=parser,
        required=required,
        gated=identifier == "good",
    )


def test_loader_contains_paths_and_keeps_one_bad_suite_partial(tmp_path):
    good = tmp_path / "evals/good.json"
    bad = tmp_path / "evals/bad.json"
    good.parent.mkdir()
    good.write_text('{"summary":{"passed":2,"total":2}}')
    bad.write_text("not json")
    definitions = (
        definition("good", "readiness", "audit", "evals/good.json", parse_readiness),
        definition(
            "bad",
            "facts",
            "development",
            "evals/bad.json",
            parse_fact_inspection,
        ),
    )

    suites, warnings = load_evaluation_suites(tmp_path, definitions)

    assert [suite.id for suite in suites] == ["good", "bad"]
    assert suites[0].status == "pass"
    assert suites[1].status == "error"
    assert warnings[0].suite_id == "bad"
    assert str(tmp_path) not in warnings[0].message


def test_loader_rejects_symlink_escape_and_oversized_file(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    root = tmp_path / "project"
    root.mkdir()
    (root / "escape.json").symlink_to(outside)
    large = root / "large.json"
    large.write_text('{"value":"' + "x" * 100 + '"}')
    definitions = (
        definition(
            "escape", "search", "audit", "escape.json", parse_readiness
        ),
        definition("large", "search", "audit", "large.json", parse_readiness),
    )

    suites, warnings = load_evaluation_suites(root, definitions, max_bytes=32)

    assert [suite.status for suite in suites] == ["error", "error"]
    assert {warning.code for warning in warnings} == {"invalid_source"}


def test_missing_optional_source_is_no_data(tmp_path):
    suites, warnings = load_evaluation_suites(
        tmp_path,
        (
            definition(
                "missing",
                "quiz",
                "smoke",
                "evals/missing.json",
                parse_readiness,
            ),
        ),
    )

    assert suites[0].status == "no_data"
    assert warnings[0].code == "missing_source"


def test_all_registered_reports_parse_without_network_or_model_calls():
    suites, warnings = load_evaluation_suites(PROJECT_ROOT)

    assert len(registered_suites()) == 10
    assert len(suites) == 10
    assert not [suite for suite in suites if suite.status == "error"]
    assert not warnings
    assert {suite.category for suite in suites} >= {
        "development",
        "held_out",
        "smoke",
        "audit",
    }
    for suite in suites:
        for metric in suite.metrics:
            if metric.unit == "percent":
                assert metric.numerator is not None
                assert metric.denominator is not None


def test_registry_is_fixed_and_has_no_absolute_paths():
    definitions = registered_suites()

    assert len({definition.id for definition in definitions}) == len(definitions)
    assert all(not Path(definition.relative_path).is_absolute() for definition in definitions)
    assert all(".." not in Path(definition.relative_path).parts for definition in definitions)
