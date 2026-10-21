"""Parallel read-only movie source acquisition with shared singleflight caching."""
import asyncio
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit,urljoin
import httpx
from .evidence_store import SourceDocument
from .movie_web_sources import make_web_source,make_provider_source,normal,duplicates
from .public_web import PublicWebReader,SourceRejected
from .web_search import FreeMovieSearch,SearchUnavailable
from .web_corpus_store import WebCorpusStore,POLICY
from .screenplay_source import SCRIPTS,load_script,script_documents,_ScreenplayHTML,normalize_script,scene_sections
from .source_sections import SourceSection

@dataclass(frozen=True)
class CorpusResult:
    sources:tuple[SourceDocument,...]
    trace:dict

class MovieSourceCorpus:
    def __init__(self,search=None,reader=None,store=None,*,script_client=None,script_cache=None,reference_client=None):
        self.search=search or FreeMovieSearch();self.reader=reader or PublicWebReader();self.store=store or WebCorpusStore()
        from .wikipedia_references import WikipediaReferenceSearch
        self.reference_search=WikipediaReferenceSearch(reference_client) if reference_client is not None else None
        self.script_client=script_client;self.script_cache=Path(script_cache or Path(__file__).resolve().parents[2]/'data/private/screenplays')
        self.pending={};self.slots=asyncio.Semaphore(2)
    async def close(self):
        tasks=list(self.pending.values())
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True);self.pending.clear()
    def key(self,movie,purpose):
        fallback=None if self.reference_search is None else self.reference_search.provider
        return hashlib.sha256(f'{POLICY}:{fallback}:{movie.fingerprint}:{purpose}:{self.search.provider}'.encode()).hexdigest()
    async def web(self,movie,purpose,*,refresh=False):
        key=self.key(movie,purpose)
        return await self._cached_web(movie,purpose,key,movie.query(purpose),refresh=refresh)
    def targeted_key(self,movie,query):
        fallback=None if self.reference_search is None else self.reference_search.provider
        return hashlib.sha256(f'{POLICY}:{fallback}:targeted-story:{movie.fingerprint}:{self.search.provider}:{query}'.encode()).hexdigest()
    async def targeted_story(self,movie,query,*,refresh=False):
        if not isinstance(query,str) or not 1<=len(query)<=500:
            raise ValueError('Targeted story query exceeds budget')
        key=self.targeted_key(movie,query)
        return await self._cached_web(movie,'story',key,query,refresh=refresh)
    async def _cached_web(self,movie,purpose,key,query,*,refresh=False):
        if not refresh:
            cached=await asyncio.to_thread(self.store.bundle,key)
            if cached:return self.restore(cached)
        task=self.pending.get(key)
        if task is None:
            task=asyncio.create_task(self._web(movie,purpose,key,query));self.pending[key]=task
            def done(completed):
                self.pending.pop(key,None)
                if not completed.cancelled():completed.exception()
            task.add_done_callback(done)
        return await asyncio.shield(task)
    def restore(self,cached):
        sources=tuple(self.store.load(r['movie_id'],r['source_id'],r['revision']) for r in cached['sources'])
        return CorpusResult(sources,{**cached['trace'],'cache':'hit'})
    async def _web(self,movie,purpose,key,query):
        async with self.slots:
            errors=[];accepted=[]
            try:
                async with asyncio.timeout(80):
                    discovery=self.search.provider
                    try:hits=await self.search.search(query,limit=15)
                    except SearchUnavailable:
                        if self.reference_search is None:raise
                        hits=await self.reference_search.search(movie,purpose,limit=30)
                        discovery=self.reference_search.provider
                    for offset in range(0,len(hits),3):
                        async def acquire(hit):
                            try:return make_web_source(movie,await self.reader.fetch(hit.url),purpose=purpose)
                            except (ValueError,OSError,TimeoutError,httpx.HTTPError) as error:return type(error).__name__
                        batch=await asyncio.gather(*(acquire(hit) for hit in hits[offset:offset+3]))
                        for hit,result in zip(hits[offset:offset+3],batch):
                            if isinstance(result,str):errors.append({'rank':hit.rank,'reason':result});continue
                            if duplicates(result,accepted):errors.append({'rank':hit.rank,'reason':'duplicate'});continue
                            host=urlsplit(result.source_ref).hostname
                            if sum(urlsplit(s.source_ref).hostname==host for s in accepted)>=2:
                                errors.append({'rank':hit.rank,'reason':'publisher_diversity'});continue
                            await asyncio.to_thread(self.store.remember,result,'web');accepted.append(result)
                            if len(accepted)==5:break
                        if len(accepted)==5:break
            except (SearchUnavailable,TimeoutError):errors.append({'rank':0,'reason':'search_unavailable'})
            old=await asyncio.to_thread(self.store.bundle,key,stale=True)
            if old:
                result=self.restore(old)
                if len(accepted)<len(result.sources):
                    return CorpusResult(result.sources,{**result.trace,'cache':'stale','errors':errors,'degraded':True})
            trace={'provider':locals().get('discovery',self.search.provider),'purpose':purpose,'requested_web_pages':5,'accepted_web_pages':len(accepted),
                   'degraded':len(accepted)<5,'errors':errors[:15],'cache':'miss','policy':POLICY}
            record={'sources':[{'movie_id':s.movie_id,'source_id':s.source_id,'revision':s.revision} for s in accepted],'trace':trace}
            await asyncio.to_thread(self.store.save_bundle,key,record,ttl=86400 if len(accepted)==5 else 600)
            return CorpusResult(tuple(accepted),trace)
    async def screenplay(self,movie):
        try:
            if movie.movie_id in SCRIPTS and self.script_client is not None:
                snapshot,_=await load_script(self.script_client,movie_id=movie.movie_id,cache_root=self.script_cache)
                docs=[source for source,_ in script_documents(snapshot)]
            else:
                from html.parser import HTMLParser
                class Links(HTMLParser):
                    def __init__(self):super().__init__();self.active=None;self.links=[];self.label=[]
                    def handle_starttag(self,tag,attrs):
                        if tag=='a':self.active=dict(attrs).get('href');self.label=[]
                    def handle_data(self,data):
                        if self.active:self.label.append(data)
                    def handle_endtag(self,tag):
                        if tag=='a' and self.active:self.links.append((self.active,''.join(self.label)));self.active=None
                index=await self.reader.fetch('https://imsdb.com/all%20scripts/')
                links=Links();links.feed(index.body.decode('utf-8',errors='replace'))
                matches=[url for url,label in links.links if normal(label)==normal(movie.title)]
                if len(matches)!=1:return CorpusResult((),{'script':'not_found'})
                detail_url=urljoin('https://imsdb.com/',matches[0])
                if urlsplit(detail_url).hostname!='imsdb.com':raise SourceRejected('Unexpected script host')
                detail=await self.reader.fetch(detail_url)
                if urlsplit(detail.url).hostname!='imsdb.com':raise SourceRejected('Unexpected script host')
                links=Links();links.feed(detail.body.decode('utf-8',errors='replace'))
                paths=[urljoin(detail.url,url) for url,_ in links.links if re.fullmatch(r'/scripts/[^/?#]+\.html',url)]
                if len(set(paths))!=1:return CorpusResult((),{'script':'unverified_link'})
                raw=await self.reader.fetch(paths[0],maximum=1000000)
                if urlsplit(raw.url).hostname!='imsdb.com':raise SourceRejected('Unexpected script host')
                parser=_ScreenplayHTML();parser.feed(raw.body.decode('utf-8',errors='replace'));parser.close()
                text=normalize_script(''.join(parser.parts))
                if not parser.done or not any(normal(line)==normal(movie.title) for line in text.splitlines()[:8]) or not 100<=len(text)<=500000:
                    raise SourceRejected('Script header identity mismatch')
                scenes=scene_sections(text);docs=[]
                for offset in range(0,len(scenes),60):
                    group=scenes[offset:offset+60];start,end=group[0].start,group[-1].end
                    if end-start>100000:raise SourceRejected('Script grouping budget exceeded')
                    sections=tuple(SourceSection(s.start-start,s.end-start,s.title,'plot') for s in group)
                    docs.append(SourceDocument(f'imsdb-{movie.movie_id}-part-{offset//60}',movie.movie_id,text[start:end],
                        f'IMSDb · {movie.title} · unverified draft',raw.url,'imsdb-'+hashlib.sha256(raw.body).hexdigest(),'spoiler',sections))
            for source in docs:await asyncio.to_thread(self.store.remember,source,'script')
            return CorpusResult(tuple(docs),{'script':'available_draft','parts':len(docs),'released_film_verified':False})
        except (ValueError,OSError,TimeoutError,httpx.HTTPError):return CorpusResult((),{'script':'unavailable'})
    async def collect(self,movie,*,purposes=('story','background'),scripts=True,refresh=False):
        tasks=[self.web(movie,p,refresh=refresh) for p in purposes]
        if scripts:tasks.append(self.screenplay(movie))
        results=await asyncio.gather(*tasks)
        provider=make_provider_source(movie)
        await asyncio.to_thread(self.store.remember,provider,'provider')
        sources={s.source_id:s for result in results for s in result.sources}
        sources[provider.source_id]=provider
        return CorpusResult(tuple(sources.values()),{'branches':[r.trace for r in results],
            'source_count':len(sources),'degraded':any(r.trace.get('degraded',False) for r in results)})
