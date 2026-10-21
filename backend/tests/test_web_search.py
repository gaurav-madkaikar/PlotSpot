import asyncio
import json

import pytest

from movie_companion.web_search import FreeMovieSearch, SearchUnavailable


class Process:
    def __init__(self, calls, available):
        self.calls=calls;self.available=available;self.returncode=None
    async def communicate(self, body):
        request=json.loads(body);provider=request['provider'];self.calls.append(provider);self.returncode=0
        payload=[] if provider not in self.available else [
            {'title':'Film source','url':'https://example.com/film','snippet':'Discovery only'}]
        return json.dumps(payload).encode(),b''
    def kill(self):self.returncode=-9
    async def wait(self):return self.returncode


def test_free_search_falls_back_between_bounded_providers(monkeypatch):
    calls=[]
    async def create(*args,**kwargs):return Process(calls,{'startpage'})
    monkeypatch.setattr(asyncio,'create_subprocess_exec',create)
    result=asyncio.run(FreeMovieSearch('duckduckgo').search('film query',limit=5))
    assert calls==['duckduckgo','startpage']
    assert result[0].url=='https://example.com/film' and result[0].rank==1


def test_free_search_reports_both_provider_failures_without_returning_empty_success(monkeypatch):
    calls=[]
    async def create(*args,**kwargs):return Process(calls,set())
    monkeypatch.setattr(asyncio,'create_subprocess_exec',create)
    with pytest.raises(SearchUnavailable):
        asyncio.run(FreeMovieSearch('startpage').search('film query',limit=5))
    assert calls==['startpage','duckduckgo']
