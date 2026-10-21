import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest

from movie_companion import content_quality_eval as evaluation
from movie_companion.content_proposal_review import DraftDecision, DraftReview


ROOT = Path(__file__).parents[2]


def dataset():
    return evaluation.QualityDataset.model_validate_json(
        (ROOT/'evals/movie-rag/content-quality-development.json').read_text())


def run(data=None, **kwargs):
    return asyncio.run(evaluation.evaluate_quality(None,dataset=data or dataset(),model='qwen3.5:9b',
        model_digest='test-digest',**kwargs))


def test_frozen_partitions_have_complete_labels_and_disjoint_cases():
    dev = dataset()
    held = evaluation.QualityDataset.model_validate_json(
        (ROOT/'evals/movie-rag/content-quality-held-out.json').read_text())
    assert dev.partition=='development' and held.partition=='held-out'
    assert sum(len(b.labels) for b in dev.batches)==18
    assert sum(len(b.labels) for b in held.batches)==12
    ids = lambda d:{b.batch_id+':'+label for b in d.batches for label in b.labels}
    assert not ids(dev) & ids(held)
    texts = lambda d:{e.text for b in d.batches for e in b.evidence}
    assert not texts(dev) & texts(held)


@pytest.mark.parametrize('change',['missing-label','extra-label','duplicate-batch','duplicate-passage'])
def test_invalid_datasets_fail_before_inference(change):
    data = dataset().model_dump()
    if change=='missing-label': del data['batches'][0]['labels']['F1']
    elif change=='extra-label': data['batches'][0]['labels']['Q9']={'decision':'accept','category':'unknown'}
    elif change=='duplicate-batch': data['batches'].append(copy.deepcopy(data['batches'][0]))
    else: data['batches'][0]['evidence'][1]['passage_id']='P1'
    with pytest.raises(ValueError): evaluation.QualityDataset.model_validate(data)


def test_metrics_distinguish_false_accepts_from_rejecting_everything():
    cases=[{'expected':'accept','actual':'reject','matched':False},
           {'expected':'reject','actual':'accept','matched':False},
           {'expected':'uncertain','actual':'error','matched':False}]
    result=evaluation.metrics(cases)
    assert result['false_acceptance']=={'count':1,'total':2}
    assert result['useful_acceptance']=={'count':0,'total':1}
    assert result['false_rejection']=={'count':1,'total':1}
    assert result['errors']=={'count':1,'total':3}
    assert evaluation.metrics([])['label_matches']=={'count':0,'total':0}


def test_report_has_identity_exact_results_and_checkpoints(monkeypatch):
    data=dataset()
    calls=[]
    async def review(*args,**kwargs):
        batch=data.batches[len(calls)]; calls.append(batch.batch_id)
        return DraftReview(items=[DraftDecision(item_id=i,decision=label.decision,
            reason='Mocked labelled decision for runner contract.') for i,label in batch.labels.items()])
    monkeypatch.setattr(evaluation.critic,'review_proposals',review)
    checkpoints=[]
    report=run(checkpoint=lambda r:checkpoints.append(copy.deepcopy(r)))
    assert report['state']=='complete'
    assert report['metrics']['label_matches']=={'count':18,'total':18}
    assert len(report['dataset_sha256'])==64 and len(report['critic_implementation_sha256'])==64
    assert len(report['batches'])==3 and report['planned_cases']==18
    assert report['model_digest']=='test-digest'
    assert report['generation_settings']['think'] is False
    assert len(checkpoints)==5 and checkpoints[0]['state']=='running'
    assert report['metrics_by_category']['unsupported-number']['label_matches']['count']==1


@pytest.mark.parametrize('failure',['http','malformed','missing-ids'])
def test_failed_judgements_remain_in_denominator_and_other_batches_continue(monkeypatch,failure):
    calls=[]
    async def review(*args,**kwargs):
        calls.append(1)
        if failure=='http': raise httpx.ReadTimeout('Local timeout')
        if failure=='malformed': raise ValueError('Invalid JSON')
        return DraftReview(items=[])
    monkeypatch.setattr(evaluation.critic,'review_proposals',review)
    report=run()
    assert len(calls)==3
    assert report['metrics']['errors']=={'count':18,'total':18}
    assert report['metrics']['label_matches']=={'count':0,'total':18}
    assert report['state']=='complete'  # completion describes runner progress, not success


def test_overall_deadline_does_not_hide_unfinished_cases(monkeypatch):
    async def review(*args,**kwargs): raise TimeoutError('Overall deadline')
    monkeypatch.setattr(evaluation.critic,'review_proposals',review)
    report=run()
    assert report['state']=='incomplete' and report['stop_reason']=='deadline_exceeded'
    assert len(report['cases'])==18
    assert report['metrics']['errors']['count']==18


def test_optional_structured_verifier_preserves_criteria_in_report(monkeypatch):
    from movie_companion import structured_content_review as structured
    data=dataset()
    data.batches=data.batches[:1]
    async def review(*args,**kwargs):
        return structured.StructuredReview(items=[structured.StructuredDecision(item_id=item_id,
            decision=label.decision,reason='Mocked assessment trace for evaluator contract.',
            assessment=structured.Assessment(item_id=item_id,support='supported',content='eligible',
                supported_option_indices=[] if item_id.startswith('F') else [0],
                plausible_options=None if item_id.startswith('F') else True,
                narrative_focus='not_applicable' if item_id.startswith('F') else 'turning_point',
                narrative_significance='not_applicable' if item_id.startswith('F') else 'central',
                reason='Mocked structured criteria for trace preservation.'))
            for item_id,label in data.batches[0].labels.items()])
    monkeypatch.setattr(structured,'review_proposals',review)
    report=run(data,reviewer_module=structured)
    assert report['critic_policy_version']==structured.REVIEW_POLICY_VERSION
    assert report['cases'][0]['assessment']['support']=='supported'


def test_fresh_reserved_sources_are_disjoint_from_consumed_partitions():
    fresh=evaluation.QualityDataset.model_validate_json(
        (ROOT/'evals/movie-rag/content-quality-held-out-v2.json').read_text())
    consumed=evaluation.QualityDataset.model_validate_json(
        (ROOT/'evals/movie-rag/content-quality-held-out.json').read_text())
    assert fresh.partition=='held-out' and sum(len(b.labels) for b in fresh.batches)==12
    previous={e.text for d in (dataset(),consumed) for b in d.batches for e in b.evidence}
    assert not previous & {e.text for b in fresh.batches for e in b.evidence}
