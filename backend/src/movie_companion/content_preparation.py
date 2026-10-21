"""Bounded generator/critic workflow producing reviewable drafts, not publications."""
import asyncio
import hashlib
import re
from pathlib import Path
from time import monotonic

import httpx

from .content_proposal_learning import GENERATION_POLICY_VERSION, propose_content
from .content_proposal_review import review_proposals
from .content_proposals import check_proposals
from .proposal_evidence import evidence_batches, verify_origins
from .preparation_resume import identity, restore, validate_plan, apply_record
from .wikipedia_source import MOVIE_ARTICLES


def duplicate_reason(item, previous, kind):
    wording = item['text'] if kind == 'fact' else item['question']
    words = set(re.findall(r'\w+', wording.casefold()))
    for other in previous:
        other_words = set(re.findall(r'\w+', (other['text'] if kind == 'fact' else other['question']).casefold()))
        if words and len(words & other_words) / len(words | other_words) >= 0.75:
            return 'overlapping_wording'
        if item['evidence_quote'] == other['evidence_quote']:
            return 'reused_evidence_quote'
    return None


async def prepare_drafts(client, *, source, model, review_model, max_batches=8,
                         deadline_seconds=600, checkpoint=None, reviewer=None,
                         evidence_loader=None, resume=None):
    if type(deadline_seconds) is not int or not 1 <= deadline_seconds <= 600:
        raise ValueError('Preparation deadline must be one to 600 seconds')
    if type(max_batches) is not int or not 1 <= max_batches <= 8:
        raise ValueError('Use one to eight evidence batches')
    selected_reviewer = reviewer or review_proposals
    report = {
        'movie_id': source.movie_id, 'generator_model': model, 'critic_model': review_model,
        'generator_policy': GENERATION_POLICY_VERSION,
        'generator_implementation_sha256': hashlib.sha256(
            Path(__file__).with_name('content_proposal_learning.py').read_bytes()).hexdigest(),
        'verifier_module':selected_reviewer.__module__,
        'source_manifest': {'source_id': source.source_id, 'source_ref': source.source_ref,
                            'revision': source.revision,
                            'text_sha256': hashlib.sha256(source.text.encode()).hexdigest()},
        'targets': {'facts': 5, 'questions': 10}, 'facts': [], 'questions': [], 'batches': [],
        'state': 'running', 'stop_reason': None, 'publication_approved': False,
        'saved_collection_changed': False,
        'evidence_mode': 'rag' if evidence_loader else 'sections',
        'phase': 'retrieving',
        **identity(source,model,review_model,selected_reviewer,max_batches),
    }
    batches = None
    if resume is not None:
        report,batches = restore(source,report,resume,duplicate_reason)
        if all(len(report[k])>=n for k,n in report['targets'].items()):
            report.update(state='needs_review',phase='finished',stop_reason='targets_reached')
        if report['state'] != 'running':
            if checkpoint:
                checkpoint(report)
            return report
    started = monotonic()

    def save():
        report['elapsed_seconds'] = round(monotonic() - started, 2)
        if checkpoint:
            checkpoint(report)

    save()
    try:
        async with asyncio.timeout(deadline_seconds):
            if batches is None and evidence_loader is not None:
                retrieved = await evidence_loader()
                batches = retrieved.batches
                if not batches or len(batches) > max_batches or any(not 1 <= len(b) <= 4 for b in batches):
                    raise ValueError('Retrieval returned invalid batch budgets')
                report['retrieval'] = retrieved.trace
                report['evidence_plan'] = [list(e.model_dump() for e in b) for b in batches]
                save()
            elif batches is None:
                batches = evidence_batches(source, max_batches=max_batches)
                report['evidence_plan'] = [[e.model_dump() for e in b] for b in batches]
            # Validate the whole plan before the first model call.
            batches = validate_plan(source,report['evidence_plan'],max_batches)
            for index, evidence in enumerate(batches):
                if index < len(report['batches']):
                    continue
                # Once only background remains and the facts target is met,
                # another model call cannot supply a missing story question.
                if not any(len(report['facts' if p.purpose == 'background' else 'questions'])
                           < report['targets']['facts' if p.purpose == 'background' else 'questions']
                           for p in evidence):
                    report['stop_reason'] = 'no_evidence_for_unmet_targets'
                    break
                verify_origins(source, evidence)
                report['phase'] = 'generating'
                save()
                proposals = await propose_content(client, model=model,
                    movie_title=MOVIE_ARTICLES[source.movie_id], evidence=evidence)
                report['phase'] = 'reviewing'
                save()
                review = await selected_reviewer(client, model=review_model,
                    proposals=proposals, evidence=evidence)
                record = {'batch': index+1, 'evidence': [e.model_dump() for e in evidence],
                          'generation_branches': [purpose for purpose in ('background', 'story')
                                                  if any(e.purpose == purpose for e in evidence)],
                          'proposals': proposals.model_dump(), 'checks': check_proposals(proposals, evidence),
                          'review': review.model_dump(), 'selection': []}
                record['selection'] = apply_record(report,record,duplicate_reason)
                report['batches'].append(record)
                save()
                if all(len(report[k]) >= n for k, n in report['targets'].items()):
                    report['stop_reason'] = 'targets_reached'
                    break
            else:
                report['stop_reason'] = 'evidence_or_batch_budget_exhausted'
    except (ValueError, httpx.HTTPError, TimeoutError) as error:
        # Retain completed batches; never retry without a budget or expose raw
        # response data in an operational error. Cancellation still propagates.
        report['stop_reason'] = 'deadline_exceeded' if isinstance(error, TimeoutError) else 'model_or_validation_failure'
        report['error_type'] = type(error).__name__
    report['state'] = 'needs_review' if report['stop_reason'] == 'targets_reached' else 'incomplete'
    report['phase'] = 'finished'
    save()
    return report
