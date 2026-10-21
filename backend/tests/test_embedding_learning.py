import asyncio
import json

import httpx
import pytest

from movie_companion.embedding_learning import embed_texts


TEXTS = ["search_document: A journey through space.", "search_document: A family dinner."]


def run_with_response(handler, texts=None):
    async def run():
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:11434",
            transport=httpx.MockTransport(handler),
            timeout=60,
        ) as client:
            return await embed_texts(
                client, model="nomic-embed-text:v1.5",
                texts=TEXTS if texts is None else texts,
            )
    return asyncio.run(run())


def test_embeds_batch_and_preserves_order():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/api/embed"
        assert json.loads(request.content) == {
            "model": "nomic-embed-text:v1.5", "input": TEXTS, "truncate": False,
        }
        return httpx.Response(200, json={"embeddings": [[0.6, 0.8], [-0.8, 0.6]]})

    assert run_with_response(handler) == [[0.6, 0.8], [-0.8, 0.6]]


def test_single_text_still_returns_nested_list():
    assert run_with_response(
        lambda request: httpx.Response(200, json={"embeddings": [[1.0, 0.0]]}),
        texts=["search_query: space exploration"],
    ) == [[1.0, 0.0]]


def test_preserves_http_error():
    with pytest.raises(httpx.HTTPStatusError):
        run_with_response(lambda request: httpx.Response(404, json={"error": "missing model"}))


@pytest.mark.parametrize("payload", [
    [], {}, {"embeddings": None}, {"embeddings": []},
    {"embeddings": [[1.0, 0.0]]},
    {"embeddings": [[], []]},
    {"embeddings": [[1.0, 0.0], [1.0]]},
    {"embeddings": [[1.0, 0.0], ["not a number", 1.0]]},
    {"embeddings": [[1.0, 0.0], [True, 1.0]]},
    {"embeddings": [[1.0, 0.0], [float("nan"), 1.0]]},
    {"embeddings": [[1.0, 0.0], [float("inf"), 1.0]]},
    {"embeddings": [[1.0, 0.0], [0.0, 0.0]]},
])
def test_rejects_invalid_vectors(payload):
    with pytest.raises(ValueError):
        run_with_response(lambda request: httpx.Response(200, json=payload))


@pytest.mark.parametrize("texts", [[], [""], ["   "], [123]])
def test_rejects_invalid_inputs_before_network(texts):
    def handler(request):
        pytest.fail("Invalid inputs should not call Ollama")

    with pytest.raises(ValueError):
        run_with_response(handler, texts=texts)
