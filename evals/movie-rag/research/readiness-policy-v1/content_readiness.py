"""Additional withholding checks; readiness never authorizes publication."""
from dataclasses import asdict

import httpx

from .background_fact_review import missing_mentions
from .background_fact_workflow import complete_source_quote, complete_support_quote
from .discussion_support import MODEL, review_support
from .proposal_evidence import verify_origins
from .quiz_novelty import normalized, review_quiz_novelty, saved_question_pairs

POLICY = 'content-citation-novelty-readiness-v1'
# These two headings were explicitly discouraged by the existing fact prompt.
# This is a small editorial rule, not a general title-quality classifier.
GENERIC_TITLES = {'visual inspiration', 'set atmosphere'}


async def fact_readiness(client, *, proposal, evidence, source, base_eligible):
    if type(base_eligible) is not bool:
        raise ValueError('Necessary eligibility must be boolean')
    problems = []
    record = {'policy': POLICY, 'ready': False, 'reasons': problems, 'support_review': None}
    if not base_eligible:
        problems.append('necessary_checks_failed')
        return record
    verify_origins(source, evidence)
    passage = next((p for p in evidence if p.passage_id == proposal.passage_id), None)
    if (passage is None or not complete_support_quote(evidence, proposal)
            or not complete_source_quote(source, passage.origin, proposal.evidence_quote)
            or not 20 <= len(proposal.evidence_quote) <= 250):
        problems.append('invalid_complete_citation')
    if normalized(proposal.title) in GENERIC_TITLES:
        problems.append('generic_title')
    if passage is not None:
        missing = missing_mentions(proposal.text, passage.model_copy(update={'text': proposal.evidence_quote}))
        if missing:
            problems.append('names_missing_from_citation')
            record['missing_mentions'] = missing
    if problems:
        return record
    try:
        # The broader retrieved paragraph is deliberately absent. A genuine
        # sentence about a related detail cannot certify the entire fact.
        result = await review_support(client, model=MODEL,
            question='What production facts are explicitly stated in the quotation, including any claimed purpose or reason?',
            answer=proposal.title+'. '+proposal.text, quotes=[proposal.evidence_quote])
        record['support_review'] = asdict(result)
        if result.verdict != 'supported':
            problems.append('citation_support_'+result.verdict)
    except (ValueError, httpx.HTTPError, TimeoutError) as error:
        problems.append('citation_review_unavailable')
        record['error_type'] = 'HTTPError' if isinstance(error, httpx.HTTPError) else type(error).__name__
    record['ready'] = not problems
    return record


async def quiz_readiness(client, *, proposals, quiz, base_eligible):
    if (not isinstance(base_eligible, list) or len(set(base_eligible)) != len(base_eligible)
            or not set(base_eligible) <= {f'Q{i+1}' for i in range(len(proposals.questions))}):
        raise ValueError('Invalid necessary quiz eligibility IDs')
    result = {'policy': POLICY, 'ready_ids': [], 'items': [], 'error_type': None}
    if not base_eligible:
        return result
    try:
        reviews = await review_quiz_novelty(client, candidates=proposals.questions,
                                           existing=saved_question_pairs(quiz))
        for review in reviews:
            ready = (review.candidate_id in base_eligible and review.novelty == 'new'
                     and review.clarity == 'clear')
            result['items'].append({**review.record(), 'ready': ready})
            if ready:
                result['ready_ids'].append(review.candidate_id)
    except (ValueError, httpx.HTTPError, TimeoutError) as error:
        result['error_type'] = 'HTTPError' if isinstance(error, httpx.HTTPError) else type(error).__name__
    return result
