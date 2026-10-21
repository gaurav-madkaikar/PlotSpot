"""Consume specialist sources through existing RAG and local reviewers serially."""
import asyncio
import hashlib
from pathlib import Path
from time import monotonic

import httpx

from .background_fact_workflow import (
    article_evidence, complete_source_quote, complete_support_quote, copied_prose,
    duplicate, propose_article_facts,
)
from .background_fact_review import review_proposals as review_facts
from .content_evidence_retrieval import MODEL, retrieve_draft_evidence
from .content_proposal_learning import propose_content
from .content_proposals import check_proposals
from .local_models import DIGESTS, verify_local_model
from .movie_research import MovieResearch, ResearchLoad, validate_load
from .proposal_evidence import verify_origins
from .structured_content_review import review_proposals
from .wikipedia_source import MOVIE_ARTICLES

POLICY = 'research-preparation-inspection-v1'
MODULES = ('movie_research.py', 'research_preparation.py', 'content_evidence_retrieval.py',
           'content_proposal_learning.py', 'structured_content_review.py',
           'background_fact_workflow.py', 'background_fact_review.py', 'background_articles.py',
           'background_registry.py', 'proposal_evidence.py', 'source_sections.py',
           'sentence_spans.py', 'ingestion_learning.py', 'evidence_store.py',
           'retrieval_learning.py', 'embedding_learning.py', 'ollama_learning.py',
           'local_models.py', 'content_proposals.py', 'wikipedia_source.py')


def implementation_hashes():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in MODULES}


async def inspect_background_sources(client, *, documents, store, saved):
    """The same article policies, with independent per-article error retention."""
    if saved is None:
        raise ValueError('Saved facts are required for novelty comparison')
    await verify_local_model(client, MODEL)
    await verify_local_model(client, 'qwen3.5:9b')
    previous = [item.text for item in saved['facts'].items]
    report = {'candidates': [], 'errors': [], 'sources': [], 'published': False}
    for document in documents:
        source = document.source
        try:
            evidence, retrieval = await article_evidence(client, store, document.article)
            verify_origins(source, evidence)
            report['sources'].append({'source_id': source.source_id, 'retrieval': retrieval,
                                      'evidence': [p.model_dump() for p in evidence]})
            proposals = await propose_article_facts(client, evidence, previous)
            if proposals.questions or len(proposals.facts) > 2:
                raise ValueError('Invalid background generation branch')
            review = await review_facts(client, model='qwen3.5:9b', proposals=proposals, evidence=evidence)
            checks = check_proposals(proposals, evidence)
            decisions = {d.item_id: d for d in review.items}
            for index, proposal in enumerate(proposals.facts):
                decision = decisions[f'F{index+1}']
                passage = next(p for p in evidence if p.passage_id == proposal.passage_id)
                eligible = (checks[index]['support_checks_passed']
                    and len(proposal.evidence_quote) <= 250
                    and complete_support_quote(evidence, proposal)
                    and complete_source_quote(source, passage.origin, proposal.evidence_quote)
                    and len(proposal.text.split()) <= 45 and decision.decision == 'accept'
                    and not copied_prose(proposal.text, proposal.evidence_quote)
                    and not duplicate(proposal.text, previous))
                report['candidates'].append({'id': source.source_id+f':F{index+1}',
                    'proposal': proposal.model_dump(), 'origin': passage.origin.model_dump(),
                    'checks': checks[index], 'review': decision.model_dump(),
                    'complete_source_sentence': complete_source_quote(source, passage.origin, proposal.evidence_quote),
                    'copied_source_prose': copied_prose(proposal.text, proposal.evidence_quote),
                    'eligible_for_review': eligible})
                if eligible:
                    previous.append(proposal.text)
        except (ValueError, KeyError, httpx.HTTPError) as error:
            report['errors'].append({'source_id': source.source_id,
                'error_type': 'HTTPError' if isinstance(error, httpx.HTTPError) else type(error).__name__})
    return report


async def inspect_research(client, *, research: MovieResearch, store, saved,
                           branch_seconds=120):
    """No ContentStore or publisher is available here. Caller owns model admission.

    Source reads have already joined. All model calls below are awaited in fixed
    story/background order, using existing prompts and critics. Expected model
    errors retain other branch results; cancellation propagates without retries.
    """
    if client.base_url != httpx.URL('http://127.0.0.1:11434') or client.follow_redirects:
        raise ValueError('Use the fixed local model client without redirects')
    if (not isinstance(research, MovieResearch) or research.movie_id not in MOVIE_ARTICLES
            or [b.purpose for b in research.branches] != ['story', 'background']
            or type(branch_seconds) not in (int, float) or not .01 <= branch_seconds <= 240):
        raise ValueError('Invalid bounded research inspection')
    # Revalidate the entire joined source plan before the first model call.
    for branch in research.branches:
        validate_load(research.movie_id, branch.purpose, ResearchLoad(branch.documents))
    initial = implementation_hashes()
    started = monotonic()
    report = {'policy': POLICY, 'implementation_sha256': initial,
              'research': research.trace(), 'models': {m: DIGESTS[m] for m in (MODEL, 'qwen3.5:9b')},
              'local_model_concurrency': 1, 'published': False, 'branches': []}
    for branch in research.branches:
        row = {'purpose': branch.purpose, 'research_status': branch.status,
               'state': 'unavailable', 'result': None}
        began = monotonic()
        if branch.documents:
            try:
                async with asyncio.timeout(branch_seconds):
                    if branch.purpose == 'story':
                        await verify_local_model(client, MODEL)
                        await verify_local_model(client, 'qwen3.5:9b')
                        source = branch.documents[0].source
                        retrieved = await retrieve_draft_evidence(client, source=source,
                                                                  store=store, max_batches=1)
                        evidence = [p for batch in retrieved.batches for p in batch if p.purpose == 'story']
                        if not evidence:
                            raise ValueError('No retrieved story evidence')
                        verify_origins(source, evidence)
                        proposals = await propose_content(client, model='qwen3.5:9b',
                            movie_title=MOVIE_ARTICLES[research.movie_id], evidence=evidence)
                        review = await review_proposals(client, model='qwen3.5:9b',
                                                        proposals=proposals, evidence=evidence)
                        checks = check_proposals(proposals, evidence)
                        decisions = {d.item_id: d.decision for d in review.items}
                        eligible = [f'Q{i+1}' for i, check in enumerate(checks)
                                    if check['support_checks_passed'] and decisions[f'Q{i+1}'] == 'accept']
                        row['result'] = {'retrieval': retrieved.trace,
                            'evidence': [p.model_dump() for p in evidence],
                            'proposals': proposals.model_dump(), 'review': review.model_dump(),
                            'checks': checks, 'eligible_for_review': eligible}
                    else:
                        row['result'] = await inspect_background_sources(client, store=store,
                            saved=saved, documents=branch.documents)
                    row['state'] = 'inspected'
                    if branch.purpose == 'background' and row['result']['errors']:
                        row['state'] = 'partial' if row['result']['sources'] else 'failed'
            except (ValueError, KeyError, httpx.HTTPError, TimeoutError) as error:
                row.update(state='timed_out' if isinstance(error, TimeoutError) else 'failed',
                           error_type='HTTPError' if isinstance(error, httpx.HTTPError) else type(error).__name__)
        row['seconds'] = round(monotonic()-began, 6)
        report['branches'].append(row)
    report['seconds'] = round(monotonic()-started, 6)
    report['code_changed_during_run'] = initial != implementation_hashes()
    if report['code_changed_during_run']:
        raise ValueError('Research implementation changed during inspection')
    return report
