"""Replaceable free search discovery. Search snippets are never evidence."""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

class SearchUnavailable(RuntimeError):pass

@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    rank: int

class FreeMovieSearch:
    def __init__(self, provider='duckduckgo', *, deadline=18):
        if provider not in ('duckduckgo','startpage','auto'):raise ValueError('Use DuckDuckGo, Startpage or auto')
        primary='duckduckgo' if provider=='auto' else provider
        secondary='startpage' if primary=='duckduckgo' else 'duckduckgo'
        self.providers=(primary,secondary)
        self.provider='+'.join(self.providers);self.deadline=deadline
        self.slot=asyncio.Semaphore(1)

    async def search(self,query,*,limit=15):
        if not isinstance(query,str) or not 1<=len(query)<=500 or type(limit) is not int or not 1<=limit<=15:
            raise ValueError('Search exceeds the public movie query budget')
        async with self.slot:
            for provider in self.providers:
                process=None
                try:
                    async with asyncio.timeout(self.deadline):
                        process=await asyncio.create_subprocess_exec(sys.executable,'-m','movie_companion.web_search_worker',
                            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,
                            env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(Path(__file__).resolve().parents[1])})
                        output,_=await process.communicate(json.dumps({'query':query,'provider':provider,'limit':limit}).encode())
                        if process.returncode or len(output)>100000:raise SearchUnavailable('Search provider unavailable')
                        payload=json.loads(output)
                        if not isinstance(payload,list) or not payload or len(payload)>limit:raise SearchUnavailable('Invalid search response')
                        return [SearchHit(r['title'],r['url'],r['snippet'],i+1) for i,r in enumerate(payload)]
                except (TimeoutError,ValueError,KeyError,OSError,SearchUnavailable):
                    pass
                finally:
                    if process is not None and process.returncode is None:
                        process.kill();await process.wait()
            raise SearchUnavailable('Search providers unavailable')
