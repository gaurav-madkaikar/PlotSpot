"""Inspect the shared local discussion pipeline against frozen development labels.

This does not author/publish a bank or qualify script-assisted generation.
Labels and snapshots must be inspected before running; no labels are inferred
from model outputs. Phrase/citation checks do not establish claim entailment.
"""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import importlib.util
import json
from pathlib import Path
from time import perf_counter
import sys

import httpx

from movie_companion.evidence_store import EvidenceStore, SourceDocument, snapshot_key
from movie_companion.grounding_learning import build_grounded_prompt
from movie_companion.ingestion_learning import ingest_source
from movie_companion.movie_qa_learning import answer_movie_question
from movie_companion.movie_questions import MovieQuestionService
from movie_companion.movie_rag_eval import MovieRagDataset, grade_case, validate_snapshot
from movie_companion.source_sections import source_chunks
from movie_companion.wikipedia_source import MOVIE_ARTICLES
from movie_companion import discussion_retrieval
from movie_companion import grounding_learning
from movie_companion import discussion_context, discussion_support, discussion_relation_context

ROOT = Path(__file__).resolve().parents[2]
EMBEDDING_MODEL = MovieQuestionService.embedding_model
CHAT_MODEL = MovieQuestionService.chat_model
CHUNK_SETTINGS = MovieQuestionService.chunk_settings
BASELINE_ROOT = ROOT/'evals/movie-rag/coverage/vector-baseline-v1'
HYBRID_BASELINE_ROOT = ROOT/'evals/movie-rag/coverage/hybrid-baseline-v6'
SUPPORT_BASELINE_ROOT = ROOT/'evals/movie-rag/coverage/support-baseline-v1'


def frozen_vector_baseline():
    """Versioned project code, never a module path selected by source/model text."""
    modules = {}
    for name in ('grounding_learning', 'movie_qa_learning'):
        module_name = f'movie_companion._frozen_discussion_{name}'
        spec = importlib.util.spec_from_file_location(module_name, BASELINE_ROOT/f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    modules['movie_qa_learning'].answer_from_hits = modules['grounding_learning'].answer_from_hits
    return modules['movie_qa_learning'].answer_movie_question


def frozen_hybrid_baseline():
    modules = {}
    for name in ('grounding_learning', 'discussion_retrieval', 'movie_qa_learning'):
        module_name = f'movie_companion._frozen_hybrid_{name}'
        spec = importlib.util.spec_from_file_location(module_name, HYBRID_BASELINE_ROOT/f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    modules['movie_qa_learning'].answer_from_hits = modules['grounding_learning'].answer_from_hits
    modules['movie_qa_learning'].retrieve_discussion_passages = modules['discussion_retrieval'].retrieve_discussion_passages
    return modules['movie_qa_learning'].answer_movie_question


def frozen_support_baseline():
    modules = {}
    for name in ('discussion_context', 'discussion_support', 'grounding_learning', 'movie_qa_learning'):
        module_name = f'movie_companion._frozen_support_{name}'
        spec = importlib.util.spec_from_file_location(module_name, SUPPORT_BASELINE_ROOT/f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    # Shared data type keeps validators compatible; its new context flag defaults
    # false, so the old builder adds no identity sentence or mandatory citation.
    modules['discussion_context'].SupportOption = discussion_context.SupportOption
    ground = modules['grounding_learning']
    ground.review_support = modules['discussion_support'].review_support
    ground.REVIEW_POLICY = modules['discussion_support'].POLICY
    pipeline = modules['movie_qa_learning']
    pipeline.answer_from_hits = ground.answer_from_hits
    pipeline.build_discussion_context = modules['discussion_context'].build_discussion_context
    return pipeline.answer_movie_question


def load_inputs(args):
    if args.output.suffix != '.json':
        raise ValueError('Use a JSON report, not an executable or snapshot file')
    if args.output.resolve() in {args.source_snapshot.resolve(), args.dataset.resolve()}:
        raise ValueError('Report must not overwrite frozen inputs')
    if args.source_snapshot.stat().st_size > 1_000_000 or args.dataset.stat().st_size > 200_000:
        raise ValueError('Evaluation input exceeds budget')
    source = SourceDocument(**json.loads(args.source_snapshot.read_text()))
    title = MOVIE_ARTICLES.get(source.movie_id)
    if (title is None or source.source_label != f'English Wikipedia contributors: {title}'
            or not source.sections or not source.source_id.startswith('enwiki-')):
        raise ValueError('Expected a registered, section-aware movie source')
    key = snapshot_key(source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
    dataset = MovieRagDataset.model_validate_json(args.dataset.read_bytes())
    ids = {f'{key[:32]}_{index:03}' for index, _ in enumerate(source_chunks(source, **CHUNK_SETTINGS))}
    validate_snapshot(dataset, key, ids)
    return source, dataset, key


async def evaluate(args):
    source, dataset, key = load_inputs(args)  # Validate frozen labels before model I/O.
    rows = []
    support = getattr(args, 'compare_support', False)
    hybrid = getattr(args, 'compare_current', False)
    baseline = frozen_support_baseline() if support else frozen_hybrid_baseline() if hybrid else frozen_vector_baseline() if getattr(args, 'compare', False) else None
    baseline_root = SUPPORT_BASELINE_ROOT if support else HYBRID_BASELINE_ROOT if hybrid else BASELINE_ROOT
    # Capture before the first inference, then detect disk changes. Never attest
    # an end-of-run file as though it were necessarily the imported code.
    tracked = [Path(m.__file__) for m in (discussion_context, discussion_support,
        discussion_retrieval, grounding_learning, discussion_relation_context)]
    tracked.append(Path(inspect.getfile(answer_movie_question)))
    initial_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False, follow_redirects=False) as client:
        tags = await client.get('/api/tags')
        tags.raise_for_status()
        digests = {m['name']: m.get('digest') for m in tags.json().get('models', [])}
        store = await asyncio.to_thread(EvidenceStore, ROOT/'backend/data/private/coverage-rag-eval')
        async with asyncio.timeout(180):
            ingestion = await ingest_source(client, store=store, source=source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
        passages = await asyncio.to_thread(store.load_snapshot, source, model=EMBEDDING_MODEL, **CHUNK_SETTINGS)
        async def inspect_case(case, pipeline, *, candidate):
            hits, answer, error = [], None, None
            traces = []
            started = perf_counter()
            try:
                async with asyncio.timeout(180):
                    answer = await pipeline(
                        client, question=case.question, passages=passages, movie_id=source.movie_id,
                        allow_spoilers=True, embedding_model=EMBEDDING_MODEL, chat_model=CHAT_MODEL,
                        on_retrieved=hits.extend,
                        **({'on_retrieval_trace': traces.append} if candidate or support else {}),
                    )
            except (ValueError, httpx.HTTPError, TimeoutError) as exc:
                error = type(exc).__name__
            context_trace = next((trace for trace in traces if trace.get('type') == 'context'), None)
            row = {
                'id': case.id, 'question': case.question, 'expected_status': case.expected_status,
                'labelled_supporting_ids': case.relevant_passage_ids,
                'retrieved': [{'passage_id': h.passage.passage_id, 'score': h.score,
                               'section': h.passage.section_title} for h in hits],
                'answer': asdict(answer) if answer else None, 'error': error,
                'duration_seconds': round(perf_counter()-started, 3),
                **grade_case(case, hits, answer, allowed_citation_ids=context_trace['generation_ids'] if context_trace else None),
                'retrieval_trace': traces[0] if traces else None,
                'grounding_trace': next((trace for trace in traces if trace.get('type') == 'grounding'), None),
                'context_trace': context_trace,
                'support_review': next((trace for trace in traces if trace.get('type') == 'support_review'), None),
            }
            return row

        for index, case in enumerate(dataset.cases):
            # Alternate the order to expose cache/warm-model effects; no model
            # calls overlap, and both arms see the same frozen source/labels.
            baseline_row = None
            if baseline is not None and index % 2 == 0:
                baseline_row = await inspect_case(case, baseline, candidate=False)
            row = await inspect_case(case, answer_movie_question, candidate=True)
            if baseline is not None and index % 2 == 1:
                baseline_row = await inspect_case(case, baseline, candidate=False)
            if baseline_row is not None:
                row['baseline'] = baseline_row
            rows.append(row)
            status = f"; baseline {'PASS' if baseline_row['automated_pass'] else 'FAIL'}" if baseline_row else ''
            print(f"{'PASS' if row['automated_pass'] else 'FAIL'} {case.id}: {row['duration_seconds']}s{status}", flush=True)
        report = {
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'initial_module_hashes': initial_hashes,
            'code_changed_during_run': any(hashlib.sha256(p.read_bytes()).hexdigest() != initial_hashes[str(p)] for p in tracked),
            'movie_id': source.movie_id, 'dataset_version': dataset.version, 'split': dataset.split,
            'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            'source_snapshot': key, 'source_revision': source.revision, 'source_ref': source.source_ref,
            'pipeline_sha256': hashlib.sha256(inspect.getsource(answer_movie_question).encode()).hexdigest(),
            'prompt_sha256': hashlib.sha256(inspect.getsource(build_grounded_prompt).encode()).hexdigest(),
            'grounding_module_sha256': hashlib.sha256(Path(grounding_learning.__file__).read_bytes()).hexdigest(),
            'retrieval_policy': discussion_retrieval.POLICY,
            'grounding_policy': grounding_learning.POLICY,
            'retriever_sha256': hashlib.sha256(Path(discussion_retrieval.__file__).read_bytes()).hexdigest(),
            'context_sha256': hashlib.sha256(Path(discussion_context.__file__).read_bytes()).hexdigest(),
            'relation_context_sha256': hashlib.sha256(Path(discussion_relation_context.__file__).read_bytes()).hexdigest(),
            'reviewer_sha256': hashlib.sha256(Path(discussion_support.__file__).read_bytes()).hexdigest(),
            'comparison': ({'order': 'alternating baseline/candidate per case; sequential',
                            'baseline_kind': 'support-v1' if support else 'hybrid-v6' if hybrid else 'vector-v1',
                            'baseline_sha256': {name: hashlib.sha256((baseline_root/f'{name}.py').read_bytes()).hexdigest()
                                               for name in (('grounding_learning', 'movie_qa_learning', 'discussion_context', 'discussion_support') if support else ('grounding_learning', 'movie_qa_learning', 'discussion_retrieval') if hybrid else ('grounding_learning', 'movie_qa_learning'))},
                            'baseline_automated_passed': sum(r['baseline']['automated_pass'] for r in rows),
                            'baseline_generation_errors': sum(r['baseline']['error'] is not None for r in rows)} if baseline else None),
            'models': {m: digests.get(m) for m in (EMBEDDING_MODEL, CHAT_MODEL, discussion_support.MODEL)},
            'chunk_settings': CHUNK_SETTINGS, 'ingestion': ingestion, 'passages': len(passages),
            'publication': False, 'token_usage': None,
            'summary': {'automated_passed': sum(r['automated_pass'] for r in rows), 'total': len(rows)},
            'limitations': ['Small development inspection, not an independent holdout or safety benchmark.',
                           'Phrase and citation membership checks do not establish entailment; inspect cited passages.',
                           'Runs the shared Wikipedia discussion function, not the HTTP or script-assisted path.',
                           'No bank generation, publication, or production throughput is measured.'],
            'cases': rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
    return 0 if all(r['automated_pass'] for r in rows) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-snapshot', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', action='store_true', help='Compare with the frozen vector-only pipeline and original prompt')
    parser.add_argument('--compare-support', action='store_true', help='Compare with the frozen sentence/reviewer pipeline from lesson 59')
    parser.add_argument('--compare-current', action='store_true', help='Compare with the frozen hybrid/excerpt pipeline from lesson 58')
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(evaluate(args)))
    except (ValueError, OSError, httpx.HTTPError, TimeoutError) as exc:
        parser.exit(2, f'Evaluation setup failed ({type(exc).__name__}): {exc}\n')
