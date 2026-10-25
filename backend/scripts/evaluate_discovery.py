"""Small labelled development set, not a held-out production benchmark."""
import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter
import httpx
from movie_companion.semantic_catalog import DEFAULT_PATH, read_index
from movie_companion.semantic_search import DiscoveryRequest, SemanticSearch, eligible

ROOT = Path(__file__).resolve().parents[2]


async def evaluate(args):
    index = read_index(args.path)
    cases = json.loads((ROOT / 'evals/discovery/cases.json').read_text())
    rows = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=35,trust_env=False,follow_redirects=False) as client:
        service = SemanticSearch(client,path=args.path)
        for case in cases:
            request = DiscoveryRequest(**{k:v for k,v in case.items() if k!='expected_movie_id'})
            started = perf_counter()
            result = await service.search(request)
            ids = [m.id for m in result.items]
            lexical = [m.id for m in index.movies if eligible(m,request) and request.query.casefold() in ' '.join([m.title,*m.cast]).casefold()]
            rows.append({**case,'returned_ids':ids,'top1_hit':ids[0]==case['expected_movie_id'] if ids else False,'top3_hit':case['expected_movie_id'] in ids[:3],'lexical_hit':case['expected_movie_id'] in lexical,'filters_satisfied':all(eligible(m,request) for m in result.items),'latency_seconds':round(perf_counter()-started,3)})
    report = {'scope':f'Legacy raw vector ranking on {len(index.movies)} indexed films with ten labelled development cases. The app now uses guarded unified search; use evaluate_unified_search.py for that path. Not held-out. Literal title/cast substring is not a tuned lexical baseline.', 'model':index.model,'catalog_fingerprint':index.fingerprint,'metadata_source':index.movies[0].source,'indexed_movies':len(index.movies),'top1_hits':sum(r['top1_hit'] for r in rows),'top3_hits':sum(r['top3_hit'] for r in rows),'lexical_hits':sum(r['lexical_hit'] for r in rows),'cases':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path',type=Path,default=DEFAULT_PATH)
    parser.add_argument('--output',type=Path,default=ROOT/'evals/discovery/local-ollama-smoke.json')
    asyncio.run(evaluate(parser.parse_args()))
