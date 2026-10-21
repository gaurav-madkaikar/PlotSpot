"""Evaluate the shipped search and raw-vector baseline on labelled development cases."""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from time import perf_counter

import httpx

from movie_companion.hybrid_retrieval import HybridRetriever
from movie_companion.local_models import DIGESTS
from movie_companion.search_reranker import OllamaReranker, CONFIG_VERSION
from movie_companion.legacy_semantic_catalog_search import CatalogQuery, search_catalog
from movie_companion.search_intent import interpret, synopsis_support, theme_support
from movie_companion.semantic_catalog import DEFAULT_PATH, read_index
from movie_companion.semantic_search import SemanticSearch
from movie_companion.vector_math import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]


def retrieval_metrics(ids, relevant):
    """Known-target retrieval; incomplete labels cannot establish precision."""
    targets = set(relevant)
    if not targets:
        return {'empty_correct': not ids}
    rank = next((i + 1 for i, mid in enumerate(ids[:20]) if mid in targets), None)
    return {
        'hit_at_1': bool(ids) and ids[0] in targets,
        'hit_at_5': bool(targets & set(ids[:5])),
        'hit_at_20': bool(targets & set(ids[:20])),
        'target_recall_at_20': len(targets & set(ids[:20])) / len(targets),
        'mrr_at_20': 1 / rank if rank else 0,
    }


def obeys_labels(movie, case):
    request = case['request']
    # Evaluate explicit filters independently of the production eligibility helper.
    return (
        (not request.get('genre') or request['genre'].casefold() in {g.casefold() for g in movie.genres})
        and (not request.get('language') or request['language'].casefold() == movie.language.casefold())
        and (not request.get('max_runtime') or movie.runtime_minutes is not None and movie.runtime_minutes <= request['max_runtime'])
        and set(case.get('required_genres', [])) <= set(movie.genres)
        and not set(case.get('excluded_genres', [])) & set(movie.genres)
    )


def aggregate(rows, system):
    completed = [r for r in rows if system in r]
    positive = [r[system] for r in completed if r['relevant_ids']]
    negative = [r[system] for r in completed if not r['relevant_ids']]
    summary = {'cases': len(rows), 'completed': len(completed), 'errors': len(rows) - len(completed), 'positive_cases': len(positive), 'empty_cases': len(negative)}
    for name in ['hit_at_1', 'hit_at_5', 'hit_at_20', 'target_recall_at_20', 'mrr_at_20']:
        summary[name] = round(sum(r['metrics'][name] for r in positive) / len(positive), 4) if positive else None
    summary['correct_empty'] = sum(r['metrics']['empty_correct'] for r in negative)
    summary['constraint_violations'] = sum(r[system]['constraint_violations'] for r in completed)
    latencies = sorted(r[system]['latency_seconds'] for r in completed)
    summary['p95_latency_seconds'] = latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else None
    return summary


async def evaluate(args):
    labels = json.loads(args.cases.read_text())
    index = read_index(args.path)
    if labels['catalog_fingerprint'] != index.fingerprint:
        raise ValueError('Catalog changed: review the labels against the new snapshot before running.')
    by_id = {m.id: m for m in index.movies}
    for case in labels['cases']:
        if not set(case['relevant_ids']) <= by_id.keys():
            raise ValueError(f"Unknown labelled movie in {case['id']}")
    rows = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=95, trust_env=False, follow_redirects=False) as client:
        service = SemanticSearch(client, path=args.path, hybrid=HybridRetriever(OllamaReranker(client, model=args.relevance_model, verify_model=True), minimum_score=args.minimum_score) if args.hybrid else None, verify_model=True)
        for case in labels['cases']:
            row = {**case}
            request = CatalogQuery(**case['request'], page_size=20)
            explicit = [m for m in index.movies if obeys_labels(m, {'request': case['request']})]
            for system in ['app', 'raw_vector']:
                started = perf_counter()
                try:
                    if system == 'app':
                        result = await search_catalog(service, request)
                        movies, total = result.items, result.total
                        row['match_type'] = result.match_type
                        if args.hybrid and result.match_type == 'semantic':
                            row['retrieval_trace'] = service.hybrid.last_trace
                        if not args.hybrid and result.match_type == 'semantic':
                            intent = interpret(request.query)
                            row['gate_excluded_target_ids'] = [mid for mid in case['relevant_ids'] if mid in {m.id for m in explicit} and not (
                                intent.required <= set(by_id[mid].genres) and not intent.excluded & set(by_id[mid].genres)
                                and theme_support(by_id[mid].title, by_id[mid].overview, intent)
                                and (synopsis_support(by_id[mid].overview, intent) > 0 or not intent.terms and (intent.required_themes or intent.excluded_themes))
                            )]
                    else:
                        # Same stored embeddings, same explicit filters, no lexical/theme gate.
                        # Reuse the query embedding cache; baseline latency is therefore warm.
                        if explicit:
                            vector = await service.query_vector(request.query, len(index.vectors[0]))
                            vectors = dict(zip((m.id for m in index.movies), index.vectors))
                            movies = sorted(explicit, key=lambda m: (-cosine_similarity(vector, vectors[m.id]), m.id))[:20]
                        else:
                            movies = []
                        total = len(explicit)
                    ids = [m.id for m in movies]
                    row[system] = {'total': total, 'top20_ids': ids, 'top5_titles': [m.title for m in movies[:5]], 'metrics': retrieval_metrics(ids, case['relevant_ids']), 'constraint_violations': sum(not obeys_labels(m, case) for m in movies), 'latency_seconds': round(perf_counter() - started, 4)}
                except Exception as error:
                    row[system + '_error'] = {'type': type(error).__name__}
            rows.append(row)
            print(f"{case['id']}: app={row.get('app', {}).get('metrics', 'error')}", flush=True)
    groups = defaultdict(list)
    for row in rows:
        groups[row['group']].append(row)
    report = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'scope': labels['scope'],
        'limitations': ['Relevant IDs are illustrative, not exhaustive; precision is not reported.', 'Raw vectors always return nearest neighbors and have no abstention threshold.', 'Baseline query embeddings may reuse the app cache; latency is not a fair system speed comparison.', 'Dataset scope is recorded above; illustrative human labels do not establish overall relevance or safety.'],
        'retrieval': {'hybrid': args.hybrid, 'minimum_score': args.minimum_score, 'model_digests': DIGESTS, 'relevance_model': args.relevance_model if args.hybrid else None, 'relevance_version': CONFIG_VERSION if args.hybrid else None, 'candidate_limit': 32 if args.hybrid else None},
        'model': index.model, 'catalog_fingerprint': index.fingerprint, 'indexed_movies': len(index.movies),
        'summary': {s: aggregate(rows, s) for s in ['app', 'raw_vector']},
        'by_group': {g: {s: aggregate(rs, s) for s in ['app', 'raw_vector']} for g, rs in groups.items()}, 'cases': rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--relevance-model', choices=['llama3.2:3b', 'qwen3.5:9b'], default='qwen3.5:9b')
    parser.add_argument('--hybrid', action='store_true')
    parser.add_argument('--minimum-score', type=float, default=2 / 3)
    parser.add_argument('--cases', type=Path, default=ROOT / 'evals/discovery/broad-cases.json')
    parser.add_argument('--path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--output', type=Path, default=ROOT / 'evals/discovery/broad-ollama-report.json')
    asyncio.run(evaluate(parser.parse_args()))
