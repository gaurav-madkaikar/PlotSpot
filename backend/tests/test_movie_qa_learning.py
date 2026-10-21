import asyncio
import json

import httpx

from movie_companion.movie_qa_learning import answer_movie_question
from movie_companion.retrieval_learning import EmbeddedPassage


def test_app_pipeline_embeds_query_retrieves_and_generates():
    calls = []
    observed = []
    passage = EmbeddedPassage("sound", 157336, "Authored fixture: a slowed washing-machine hum.", [1.0, 0.0], "nomic-embed-text:v1.5", "Fixture", "safe")
    def handler(request):
        calls.append(request.url.path)
        if request.url.path=='/api/tags':
            from movie_companion.local_models import DIGESTS
            return httpx.Response(200,json={'models':[{'name':'qwen3.5:9b','digest':DIGESTS['qwen3.5:9b']}]})
        body = json.loads(request.content)
        if request.url.path == "/api/embed":
            assert body["input"] == ["search_query: How was sound made?"]
            return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})
        assert request.url.path == "/api/chat"
        if 'verdict' in body['format']['properties']:
            return httpx.Response(200, json={'message': {'content': json.dumps({'verdict':'supported','reason':'Fixture support','evidence_answer':'A hum.','evidence_quotes':[passage.text]})}})
        assert passage.text in body["messages"][0]["content"]
        return httpx.Response(200, json={"message": {"content": json.dumps({"status": "answered", "answer": "A slowed washing-machine hum.", "evidence_quotes": [passage.text]})}})
    async def run():
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler)) as client:
            result = await answer_movie_question(client, question="How was sound made?", passages=[passage], movie_id=157336, allow_spoilers=False, embedding_model="nomic-embed-text:v1.5", chat_model="llama3.2:3b", on_retrieved=observed.extend)
            assert result.citation_ids == ("sound",)
    asyncio.run(run())
    assert calls == ["/api/embed", "/api/chat", "/api/tags", "/api/chat"]
    assert [hit.passage.passage_id for hit in observed] == ["sound"]
