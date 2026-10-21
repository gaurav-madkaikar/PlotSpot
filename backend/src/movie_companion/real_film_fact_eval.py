"""Read-only real-source challenge and generation inspection, without publication."""
import asyncio
import hashlib
import json
from pathlib import Path
from time import monotonic

import httpx
from pydantic import Field, model_validator

from . import background_fact_workflow as workflow
from . import background_fact_review
from .background_fact_review import review_proposals
from .content_proposals import StrictRecord, check_proposals
from .content_quality_eval import QualityDataset, evaluate_quality
from .evidence_store import SourceDocument
from .local_models import DIGESTS
from .proposal_evidence import evidence_pools, verify_origins

LIMITATIONS = (
    'Fresh assistant-authored real-film challenge labels frozen before the first run; '
    'consumed development evidence after inference, not independent external annotations. '
    'Short Wikipedia production excerpts, not full retrieval, publisher reliability, '
    'prompt-injection coverage or catalog-wide generation accuracy. Generated proposals '
    'are unlabelled observations requiring separate inspection. No publication permissions.'
)


class SnapshotIdentity(StrictRecord):
    movie_id: int = Field(gt=0)
    snapshot_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: str = Field(min_length=1, max_length=100)
    source_ref: str = Field(min_length=1, max_length=500)


class RealFilmDataset(StrictRecord):
    sources: list[SnapshotIdentity] = Field(min_length=1, max_length=12)
    quality: QualityDataset

    @model_validator(mode='after')
    def movie_coverage(self):
        ids = [s.movie_id for s in self.sources]
        if len(ids) != len(set(ids)) or self.quality.partition != 'development':
            raise ValueError('Unique movie identities and development labels are required')
        covered = []
        for batch in self.quality.batches:
            movie_ids = {e.origin.movie_id for e in batch.evidence if e.origin}
            if (len(movie_ids) != 1 or any(e.origin is None or e.purpose != 'background'
                                         for e in batch.evidence)
                    or not batch.proposals.facts or batch.proposals.questions):
                raise ValueError('Each batch needs background facts and one movie with exact origins')
            covered.extend(movie_ids)
        if len(covered) != len(set(covered)) or set(covered) != set(ids):
            raise ValueError('Exactly one batch must cover each snapshot movie')
        return self


def load_dataset(path: Path, snapshot_directory: Path):
    if path.stat().st_size > 1_000_000:
        raise ValueError('Evaluation dataset exceeds the input budget')
    data = RealFilmDataset.model_validate_json(path.read_text())
    sources = {}
    for identity in data.sources:
        # File names are code-owned numeric movie IDs, never model/user URLs.
        snapshot = snapshot_directory / f'{identity.movie_id}.json'
        if snapshot.stat().st_size > 1_000_000:
            raise ValueError('Snapshot exceeds the input budget')
        raw = snapshot.read_bytes()
        if hashlib.sha256(raw).hexdigest() != identity.snapshot_sha256:
            raise ValueError('Source snapshot hash changed')
        source = SourceDocument(**json.loads(raw))
        if (source.movie_id != identity.movie_id or source.revision != identity.revision
                or source.source_ref != identity.source_ref):
            raise ValueError('Source snapshot identity changed')
        evidence_pools(source)  # Enforce the registered article and revision contract.
        sources[source.movie_id] = source
    for batch in data.quality.batches:
        verify_origins(sources[batch.evidence[0].origin.movie_id], batch.evidence)
    return data


async def inspect_generation(client, *, dataset, deadline_seconds=360, checkpoint=None):
    if type(deadline_seconds) is not int or not 1 <= deadline_seconds <= 600:
        raise ValueError('Use a one to 600 second inspection deadline')
    report = {'state': 'running', 'planned_movies': len(dataset.quality.batches), 'movies': [],
              'publication_approved': False, 'limitations': LIMITATIONS}
    started = monotonic()

    def save():
        report['elapsed_seconds'] = round(monotonic() - started, 2)
        report['observations'] = {
            'completed_movies': sum(r['error_type'] is None for r in report['movies']),
            'error_movies': sum(r['error_type'] is not None for r in report['movies']),
            'proposed_facts': sum(len(r.get('proposals', {}).get('facts', [])) for r in report['movies']),
            'eligible_drafts': sum(sum(i['eligible_draft'] for i in r.get('decisions', []))
                                   for r in report['movies']),
        }
        if checkpoint:
            checkpoint(report)

    save()
    completed = set()
    try:
        async with asyncio.timeout(deadline_seconds):
            for batch in dataset.quality.batches:
                tick = monotonic()
                row = {'movie_id': batch.evidence[0].origin.movie_id, 'batch_id': batch.batch_id,
                       'error_type': None, 'evidence': [e.model_dump() for e in batch.evidence]}
                try:
                    # Excludes test proposals and labels from both model calls.
                    proposals = await workflow.propose_article_facts(client, batch.evidence, [])
                    row['proposals'] = proposals.model_dump()
                    checks = check_proposals(proposals, batch.evidence)
                    row['checks'] = checks
                    reviews = await review_proposals(client, model=workflow.MODEL,
                                                     proposals=proposals, evidence=batch.evidence)
                    by_id = {r.item_id: r for r in reviews.items}
                    if set(by_id) != {f'F{i+1}' for i in range(len(proposals.facts))}:
                        raise ValueError('Incomplete generated-fact review')
                    row['decisions'] = []
                    previous = []
                    for index, fact in enumerate(proposals.facts):
                        review = by_id[f'F{index+1}']
                        problems = list(checks[index]['problems'])
                        if len(fact.text.split()) > 45:
                            problems.append('too_many_words')
                        if len(fact.evidence_quote) > 250:
                            problems.append('quote_too_long')
                        if not workflow.complete_support_quote(batch.evidence, fact):
                            problems.append('incomplete_support_quote')
                        if workflow.copied_prose(fact.text, fact.evidence_quote):
                            problems.append('copied_prose')
                        if workflow.duplicate(fact.text, previous):
                            problems.append('duplicate_text')
                        previous.append(fact.text)
                        row['decisions'].append({**review.model_dump(), 'problems': problems,
                                                 'eligible_draft': review.decision == 'accept' and not problems})
                except (ValueError, httpx.HTTPError) as error:
                    row['error_type'] = type(error).__name__
                row['elapsed_seconds'] = round(monotonic()-tick, 2)
                report['movies'].append(row)
                completed.add(batch.batch_id)
                save()
    except TimeoutError:
        report['stop_reason'] = 'deadline_exceeded'
    for batch in dataset.quality.batches:
        if batch.batch_id not in completed:
            report['movies'].append({'movie_id': batch.evidence[0].origin.movie_id,
                                     'batch_id': batch.batch_id, 'error_type': 'NotCompleted'})
    report['state'] = 'complete' if len(completed) == len(dataset.quality.batches) else 'incomplete'
    save()
    return report


async def evaluate_real_facts(client, *, dataset, deadline_seconds=360, checkpoint=None,
                              generation_only=False):
    if type(generation_only) is not bool:
        raise ValueError('Select a boolean generation-only mode')
    report = {'dataset_sha256': hashlib.sha256(json.dumps(dataset.model_dump(), sort_keys=True,
                                                         ensure_ascii=False).encode()).hexdigest(),
              'sources': [s.model_dump() for s in dataset.sources],
              'background_policy_sha256': workflow.fingerprint(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'model': workflow.MODEL, 'model_digest': DIGESTS[workflow.MODEL],
              'mode': 'generation-only' if generation_only else 'challenge-and-generation',
              'publication_approved': False, 'state': 'running', 'limitations': LIMITATIONS}

    def save(part, result):
        report[part] = result
        if checkpoint:
            checkpoint(report)

    if not generation_only:
        report['quality'] = await evaluate_quality(client, dataset=dataset.quality, model=workflow.MODEL,
            model_digest=DIGESTS[workflow.MODEL], deadline_seconds=deadline_seconds,
            limitations=LIMITATIONS, reviewer_module=background_fact_review, checkpoint=lambda r: save('quality', r))
    report['generation'] = await inspect_generation(client, dataset=dataset,
        deadline_seconds=deadline_seconds, checkpoint=lambda r: save('generation', r))
    report['state'] = ('complete' if report.get('quality', {'state': 'complete'})['state'] == report['generation']['state'] == 'complete'
                       else 'incomplete')
    if checkpoint:
        checkpoint(report)
    return report
