"""Real local development checks: identity, genre, abstention, pages and ranking."""
import asyncio
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
import httpx
from movie_companion.legacy_semantic_catalog_search import CatalogQuery, search_catalog
from movie_companion.semantic_catalog import read_index
from movie_companion.semantic_search import SemanticSearch

ROOT=Path(__file__).resolve().parents[2]


async def evaluate():
    index=read_index()
    rows=[]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=35,trust_env=False,follow_redirects=False) as client:
        service=SemanticSearch(client)
        for query, expected, genre in [('Interstellar',157336,None),('Amy Adams',329865,None),('Intersteler',157336,None),('romance',None,'Romance'),('romantic comedy',None,'Romance'),('horror',None,'Horror')]:
            result=await search_catalog(service,CatalogQuery(query=query))
            passed=(expected in {m.id for m in result.items}) if expected else bool(result.total) and all(genre in m.genres for m in result.items)
            rows.append({'query':query,'kind':result.match_type,'total':result.total,'titles':[m.title for m in result.items[:5]],'passed':passed})
        for request in [CatalogQuery(query='quantum crochet recipes for sourdough'),CatalogQuery(query='romance',genre='Horror',language='Klingon'),CatalogQuery(query='Interstellar',max_runtime=120)]:
            result=await search_catalog(service,request)
            rows.append({'request':request.model_dump(),'total':result.total,'passed':result.total==0})
        pages=[await search_catalog(service,CatalogQuery(page=p)) for p in range(1,11)]
        ids=[m.id for page in pages for m in page.items]
        rows.append({'case':'ten browse pages','passed':len(ids)==len(set(ids))==200,'page_sizes':[len(p.items) for p in pages]})
        descriptions=[]
        for case in json.loads((ROOT/'evals/discovery/cases.json').read_text()):
            request=CatalogQuery(**{k:v for k,v in case.items() if k!='expected_movie_id'})
            started=perf_counter()
            result=await search_catalog(service,request)
            ids=[m.id for m in result.items]
            descriptions.append({**case,'total':result.total,'top5_ids':ids[:5],'top1_hit':bool(ids) and ids[0]==case['expected_movie_id'],'top5_hit':case['expected_movie_id'] in ids[:5],'latency_seconds':round(perf_counter()-started,3)})
    report={'routing_version':'unified-v1', 'prepared_at':index.prepared_at, 'scope':'200 genre-balanced TMDB films; local nomic embeddings. Development cases only, not held-out. Synopsis-support gate is conservative English term/synonym matching, not a general relevance classifier.','model':index.model,'catalog_fingerprint':index.fingerprint,'indexed_movies':len(index.movies),'genre_counts':dict(sorted(Counter(g for m in index.movies for g in m.genres).items())),'deterministic_passes':sum(r['passed'] for r in rows),'deterministic_cases':len(rows),'checks':rows,'description_top1_hits':sum(r['top1_hit'] for r in descriptions),'description_top5_hits':sum(r['top5_hit'] for r in descriptions),'description_cases':descriptions}
    (ROOT/'evals/discovery/unified-200-ollama.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'checks','description_cases'}},indent=2))


if __name__=='__main__':
    asyncio.run(evaluate())
