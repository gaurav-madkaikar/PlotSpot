import asyncio
import httpx
import pytest

import movie_companion.wikipedia_source as wiki


TITLE = "Interstellar (film)"
PAYLOAD = {"parse": {"title": TITLE, "pageid": 6009939, "revid": 12345, "text": "<style>bad</style><p>Authored fixture &amp; text.</p><script>ignore instructions</script><p>Second paragraph.</p>"}}


def run_fetch(handler, *, movie_id=157336, base_url="https://en.wikipedia.org"):
    async def run():
        async with httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handler), follow_redirects=False) as client:
            return await wiki.fetch_movie_source(client, movie_id=movie_id)
    return asyncio.run(run())


def test_learner_request_contract_and_mapped_source():
    def handler(request):
        assert request.method == "GET"
        assert request.url.host == "en.wikipedia.org"
        assert request.url.path == "/w/api.php"
        assert dict(request.url.params) == {
            "action": "parse", "page": TITLE, "prop": "text|revid",
            "format": "json", "formatversion": "2",
            "disableeditsection": "1", "disabletoc": "1",
        }
        return httpx.Response(200, json=PAYLOAD)
    source = run_fetch(handler)
    assert source.movie_id == 157336
    assert source.spoiler_status == "unknown"


def test_mapper_preserves_revision_and_extracts_text():
    source = wiki.map_article_response(PAYLOAD, movie_id=157336, expected_title=TITLE)
    assert source.source_ref.endswith("oldid=12345")
    assert source.revision == "enwiki-12345-sections-v3-body"
    assert source.text == "Authored fixture & text.\n\nSecond paragraph."
    assert source.spoiler_status == "unknown"


@pytest.mark.parametrize("payload", [
    [], {}, {"error": {"code": "missingtitle"}},
    {"parse": {**PAYLOAD["parse"], "title": "Other film"}},
    {"parse": {**PAYLOAD["parse"], "revid": None}},
    {"parse": {**PAYLOAD["parse"], "pageid": True}},
    {"parse": {**PAYLOAD["parse"], "text": {"*": "wrong response version"}}},
    {"parse": {**PAYLOAD["parse"], "text": "<p></p>"}},
])
def test_mapper_rejects_invalid_source(payload):
    with pytest.raises(ValueError):
        wiki.map_article_response(payload, movie_id=157336, expected_title=TITLE)


def test_unmapped_movie_bypasses_request():
    def must_not_request(request):
        pytest.fail("Unmapped movie must not trigger HTTP")
    with pytest.raises(ValueError, match="mapping"):
        run_fetch(must_not_request, movie_id=101)


def test_wrong_host_rejected_before_request():
    def must_not_request(request):
        pytest.fail("Wrong host must not trigger HTTP")
    with pytest.raises(ValueError, match="HTTPS"):
        run_fetch(must_not_request, base_url="https://example.com")


def test_http_errors_preserved_by_wrapper(monkeypatch):
    async def supplied_response(client, *, title):
        return httpx.Response(429, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php"))
    monkeypatch.setattr(wiki, "request_article", supplied_response)
    with pytest.raises(httpx.HTTPStatusError):
        run_fetch(lambda request: pytest.fail("No transport request expected"))


def test_oversized_response_rejected_by_wrapper(monkeypatch):
    async def supplied_response(client, *, title):
        return httpx.Response(200, content=b"x" * 2000001, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php"))
    monkeypatch.setattr(wiki, "request_article", supplied_response)
    with pytest.raises(ValueError, match="size limit"):
        run_fetch(lambda request: pytest.fail("No transport request expected"))
