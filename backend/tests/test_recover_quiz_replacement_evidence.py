import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from movie_companion.movie_web_sources import MovieIdentity
from movie_companion.quiz_replacement_completion import NarrativeIntent


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/recover_quiz_replacement_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("quiz_replacement_recovery", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def intent():
    return NarrativeIntent(
        question_id="q1",
        focus="the consequence for the family",
        relation="consequence",
        required_concepts=[["family"], ["shelter", "displaced"]],
        forbidden_details=[],
        expected_answer_shape="outcome",
    )


def target():
    return {
        "movie_id": 1,
        "title": "Flood Film",
        "question_id": "q1",
        "old_question": "Where do they go?",
        "replacement_brief": "Test the consequence of the flood for the family.",
        "evidence": {"explanation": "The family is displaced."},
    }


def evidence(label):
    return {
        "source_id": label,
        "source_label": "Publisher · Flood Film",
        "source_ref": f"https://{label}.example/story",
        "revision": f"r-{label}",
        "section_title": "Plot",
        "excerpt": "The flood displaces the family and forces them into temporary shelter.",
        "bm25": 3.0,
        "publisher": f"{label}.example",
        "source_kind": "web",
    }


def test_recovery_records_local_baseline_and_targeted_sources(monkeypatch):
    calls = []

    def retrieve(store, value, *, intent, limit):
        calls.append((store, value["question_id"], limit))
        rows = [evidence("local")]
        if len(calls) == 2:
            rows.append(evidence("targeted"))
        return rows, {"selected": len(rows), "query_terms": ["family", "shelter"]}

    class Corpus:
        async def targeted_story(self, movie, query):
            assert movie.title == "Flood Film" and query.startswith('"Flood Film"')
            return SimpleNamespace(sources=(object(),), trace={"accepted_web_pages": 1})

    monkeypatch.setattr(MODULE, "retrieve_replacement_evidence", retrieve)
    row = asyncio.run(
        MODULE.recover_target(
            Corpus(),
            object(),
            MovieIdentity(1, "Flood Film", 2024),
            target(),
            intent(),
            revision=1,
        )
    )

    assert [item["source_id"] for item in row["evidence"]] == ["local", "targeted"]
    assert row["acquisition"]["attempted"] is True
    assert row["acquisition"]["error_type"] is None
    assert row["retrieval_before"]["selected"] == 1
    assert row["retrieval"]["selected"] == 2


def test_source_failure_is_isolated_and_local_evidence_is_retained(monkeypatch):
    def retrieve(*args, **kwargs):
        return [evidence("local")], {"selected": 1}

    class Corpus:
        async def targeted_story(self, movie, query):
            raise TimeoutError("source timed out")

    monkeypatch.setattr(MODULE, "retrieve_replacement_evidence", retrieve)
    row = asyncio.run(
        MODULE.recover_target(
            Corpus(),
            object(),
            MovieIdentity(1, "Flood Film", 2024),
            target(),
            intent(),
            revision=2,
        )
    )

    assert row["evidence"] == [evidence("local")]
    assert row["acquisition"]["error_type"] == "TimeoutError"
    assert row["acquisition"]["revision"] == 2
