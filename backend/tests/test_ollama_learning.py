import asyncio

import httpx
import pytest

from movie_companion.ollama_learning import chat_once


def run_with_response(handler):
    async def run():
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:11434",
            transport=httpx.MockTransport(handler),
            timeout=60,
        ) as client:
            return await chat_once(
                client, model="llama3.2:3b", prompt="Explain embeddings briefly."
            )
    return asyncio.run(run())


def test_sends_nonstreaming_chat_and_returns_text():
    import json

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "llama3.2:3b"
        assert body["stream"] is False
        assert body["messages"] == [
            {"role": "user", "content": "Explain embeddings briefly."}
        ]
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "A vector representation."}, "done": True}
        )

    assert run_with_response(handler) == "A vector representation."


def test_preserves_http_failure():
    with pytest.raises(httpx.HTTPStatusError):
        run_with_response(lambda request: httpx.Response(404, json={"error": "model not found"}))


@pytest.mark.parametrize("payload", [
    {}, [], {"message": None}, {"message": []},
    {"message": {}}, {"message": {"content": ""}},
    {"message": {"content": "   "}}, {"message": {"content": 123}},
])
def test_rejects_missing_or_invalid_text(payload):
    with pytest.raises(ValueError):
        run_with_response(lambda request: httpx.Response(200, json=payload))
