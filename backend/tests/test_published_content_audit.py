import copy

import pytest

from movie_companion.content_store import ContentStore
from movie_companion.published_content_audit import audit_published_content, render_markdown
from movie_companion.research_checkpoint import digest
from movie_companion.source_registry import CALTECH_URL
from test_content_store import fixture_collection


def published_fixture(tmp_path):
    source, (quiz, facts) = fixture_collection()
    second = quiz.items[0].citations[0].model_copy(update={
        "source_label": "Caltech fixture",
        "source_ref": CALTECH_URL,
        "revision": "caltech-fixture",
    })
    quiz.items[0].citations.append(second)
    facts.items[0].citations.append(second)
    manifest = {source.revision: source.source_ref, second.revision: second.source_ref}
    store = ContentStore(tmp_path / "content.db")
    report_sha = "a" * 64
    receipt = store.publish_with_receipt(
        157336, job_id="b" * 32, selection_sha256="c" * 64,
        report_sha256=report_sha, reviewer="Test reviewer",
        review_kind="assistant_source_review", version="research-test",
        source_revision=source.revision, quiz=quiz, facts=facts,
        expected_prepared_at=None, source_manifest=manifest,
    )
    review = {
        "policy": "assistant-source-review-prepublication-v1",
        "movie_count": 1,
        "movies": [{"movie_id": 157336, "title": "Interstellar",
                    "job_id": "b" * 32, "report_sha256": report_sha,
                    "combined_facts": 5, "combined_questions": 10}],
    }
    publication = {
        "policy": "reviewed-research-publication-v1",
        "review_audit_sha256": digest(review),
        "movie_count": 1,
        "all_published": True,
        "receipts": [receipt],
    }
    return store, review, publication


def test_audit_verifies_receipt_payload_quotas_and_publishers(tmp_path):
    store, review, publication = published_fixture(tmp_path)
    report = audit_published_content(review_audit=review, publication_log=publication, bank=store)
    assert report["status"] == "pass"
    assert report["metrics"]["facts"] == 5
    assert report["metrics"]["scored_questions"] == 10
    assert report["metrics"]["verified_receipts"] == 1
    assert report["metrics"]["verified_payloads"] == 1
    assert report["metrics"]["movies_with_multi_publisher_facts"] == 1
    assert report["metrics"]["movies_with_multi_publisher_quiz"] == 1
    markdown = render_markdown(report)
    assert "Interstellar" in markdown and "semantic" in markdown


@pytest.mark.parametrize("change", ["audit-hash", "report-hash", "payload-hash", "missing-movie"])
def test_audit_rejects_inconsistent_publication_evidence(tmp_path, change):
    store, review, publication = published_fixture(tmp_path)
    broken = copy.deepcopy(publication)
    if change == "audit-hash": broken["review_audit_sha256"] = "0" * 64
    if change == "report-hash": broken["receipts"][0]["report_sha256"] = "0" * 64
    if change == "payload-hash": broken["receipts"][0]["payload_sha256"] = "0" * 64
    if change == "missing-movie": broken["receipts"] = []
    with pytest.raises(ValueError):
        audit_published_content(review_audit=review, publication_log=broken, bank=store)
