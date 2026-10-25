"""Labelled critic evaluation: decision quality and useful-answer coverage."""
import asyncio
import hashlib
import json
from pathlib import Path
from time import monotonic
from typing import Literal

import httpx
from pydantic import Field, model_validator

from . import content_proposal_review as critic
from .content_proposals import ContentProposals, ProposalEvidence, StrictRecord, validate_evidence


class QualityLabel(StrictRecord):
    decision: Literal['accept', 'reject', 'uncertain']
    category: str = Field(min_length=1, max_length=100)


class QualityBatch(StrictRecord):
    batch_id: str = Field(pattern=r'^[a-z0-9-]{1,64}$')
    evidence: list[ProposalEvidence] = Field(min_length=1, max_length=8)
    proposals: ContentProposals
    labels: dict[str, QualityLabel]

    @model_validator(mode='after')
    def labelled_items(self):
        validate_evidence(self.evidence)
        ids = {f'{prefix}{i+1}' for prefix, items in [('F',self.proposals.facts),('Q',self.proposals.questions)]
               for i in range(len(items))}
        if not ids or set(self.labels) != ids:
            raise ValueError('Every proposal requires exactly one label')
        return self


class QualityDataset(StrictRecord):
    dataset_version: str = Field(min_length=1, max_length=100)
    partition: Literal['development', 'held-out']
    label_policy: str = Field(min_length=20, max_length=1000)
    batches: list[QualityBatch] = Field(min_length=1, max_length=12)

    @model_validator(mode='after')
    def unique_batches(self):
        if len({b.batch_id for b in self.batches}) != len(self.batches):
            raise ValueError('Batch identities must be unique')
        return self


def metrics(cases):
    def ratio(rows, predicate):
        return {'count':sum(predicate(r) for r in rows), 'total':len(rows)}
    accepted = [r for r in cases if r['expected'] == 'accept']
    invalid = [r for r in cases if r['expected'] != 'accept']
    return {'label_matches':ratio(cases,lambda r:r['matched']),
            'useful_acceptance':ratio(accepted,lambda r:r['actual']=='accept'),
            'false_acceptance':ratio(invalid,lambda r:r['actual']=='accept'),
            'false_rejection':ratio(accepted,lambda r:r['actual']=='reject'),
            'uncertain':ratio(cases,lambda r:r['actual']=='uncertain'),
            'errors':ratio(cases,lambda r:r['actual']=='error')}


async def evaluate_quality(client, *, dataset, model, model_digest, deadline_seconds=360, checkpoint=None,
                           reviewer_module=None, limitations=None):
    reviewer_module = reviewer_module or critic
    dataset = QualityDataset.model_validate(dataset.model_dump())
    if type(deadline_seconds) is not int or not 1 <= deadline_seconds <= 600:
        raise ValueError('Use a one to 600 second evaluation deadline')
    canonical = json.dumps(dataset.model_dump(),sort_keys=True,ensure_ascii=False).encode()
    report = {'dataset_version':dataset.dataset_version, 'dataset_sha256':hashlib.sha256(canonical).hexdigest(),
              'partition':dataset.partition, 'model':model, 'model_digest':model_digest,
              'critic_policy_version':reviewer_module.REVIEW_POLICY_VERSION,
              'critic_implementation_sha256':hashlib.sha256(Path(reviewer_module.__file__).read_bytes()).hexdigest(),
              'generation_settings':{'temperature':0,'seed':7,'num_predict':1800,
                                     'think':False if model=='qwen3.5:9b' else None},
              'state':'running', 'cases':[], 'batches':[],
              'planned_cases':sum(len(b.labels) for b in dataset.batches),
              'deadline_seconds':deadline_seconds,
              'limitations':limitations or 'Authored synthetic cases; reserved held-out cases were not used for prompt revision. '
                             'Not independent external annotations, a real-movie benchmark, or a tool-security assessment. '
                             'Token counts are unavailable from the current chat helper. No publication permissions.'}
    started = monotonic()

    def record(batch, actual, elapsed, error=None):
        report['batches'].append({'batch_id':batch.batch_id,'elapsed_seconds':elapsed,'error_type':error})
        for item_id, label in batch.labels.items():
            decision = actual.get(item_id)
            report['cases'].append({'case_id':batch.batch_id+':'+item_id,'expected':label.decision,
                'category':label.category,'actual':decision.decision if decision else 'error',
                'reason':decision.reason if decision else 'No valid judgement returned.',
                'matched':bool(decision and decision.decision==label.decision)})
            if decision is not None and getattr(decision,'assessment',None) is not None:
                report['cases'][-1]['assessment']=decision.assessment.model_dump()

    def save():
        report['metrics'] = metrics(report['cases'])
        categories = {r['category'] for r in report['cases']}
        report['metrics_by_category'] = {category:metrics([r for r in report['cases'] if r['category']==category])
                                         for category in sorted(categories)}
        report['elapsed_seconds'] = round(monotonic()-started,2)
        if checkpoint: checkpoint(report)

    save()
    completed = set()
    try:
        async with asyncio.timeout(deadline_seconds):
            for batch in dataset.batches:
                tick = monotonic()
                try:
                    result = await reviewer_module.review_proposals(client,model=model,
                        proposals=batch.proposals,evidence=batch.evidence)
                    actual = {d.item_id:d for d in result.items}
                    if set(actual) != set(batch.labels):
                        raise ValueError('Incomplete judgement set')
                    record(batch,actual,round(monotonic()-tick,2))
                except (ValueError,httpx.HTTPError) as error:
                    record(batch,{},round(monotonic()-tick,2),type(error).__name__)
                completed.add(batch.batch_id)
                save()
    except TimeoutError:
        report['stop_reason'] = 'deadline_exceeded'
    for batch in dataset.batches:
        if batch.batch_id not in completed:
            record(batch,{},None,'NotCompleted')
    report['state'] = 'complete' if len(completed)==len(dataset.batches) else 'incomplete'
    save()
    return report
