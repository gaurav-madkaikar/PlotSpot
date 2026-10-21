"""Check evaluator arithmetic independently of any model response."""
from pathlib import Path
import runpy

functions = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/evaluate_broad_search.py'))
metrics = functions['retrieval_metrics']
aggregate = functions['aggregate']


def test_retrieval_metrics_count_labelled_targets_and_rank():
    result = metrics([99, 7, 8], [7, 42])
    assert result == {'hit_at_1': False, 'hit_at_5': True, 'hit_at_20': True, 'target_recall_at_20': .5, 'mrr_at_20': .5}
    assert metrics([99] * 20 + [7], [7])['hit_at_20'] is False
    assert metrics([], [7])['mrr_at_20'] == 0
    assert metrics([], []) == {'empty_correct': True}
    assert metrics([7], []) == {'empty_correct': False}


def test_summary_keeps_failures_and_empty_cases_separate():
    def output(ids, relevant):
        return {'metrics': metrics(ids, relevant), 'constraint_violations': 0, 'latency_seconds': .1}
    rows = [
        {'relevant_ids': [7], 'app': output([7], [7])},
        {'relevant_ids': [7], 'app': output([], [7])},
        {'relevant_ids': [], 'app': output([], [])},
        {'relevant_ids': [7], 'app_error': {'type': 'TimeoutError'}},
    ]
    summary = aggregate(rows, 'app')
    assert summary['cases'] == 4 and summary['completed'] == 3 and summary['errors'] == 1
    assert summary['hit_at_5'] == .5 and summary['correct_empty'] == 1
    assert summary['positive_cases'] == 2 and summary['empty_cases'] == 1
