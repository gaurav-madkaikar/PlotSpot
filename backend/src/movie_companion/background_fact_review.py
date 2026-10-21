"""Existing semantic critic plus conservative source-local multiword-name checks."""
import re
from typing import Literal
import unicodedata

import httpx
from pydantic import Field

from .content_proposal_review import DraftDecision, DraftReview
from .content_proposals import StrictRecord, check_proposals, validate_evidence
from .structured_content_review import review_proposals as semantic_review
from .wikipedia_source import MOVIE_ARTICLES

REVIEW_POLICY_VERSION = 'background-precision-critic-v5-scope-and-source-names'
# This is a narrow English/Latin capitalization heuristic, not general entity
# recognition. Single names, aliases, initials and other scripts remain a limit.
WORD = r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[-’'][A-ZÀ-ÖØ-Þ]?[a-zà-öø-ÿ]+)*"
INITIAL = r'[A-ZÀ-ÖØ-Þ]\.'
NAME = re.compile(r'\b'+WORD+r'(?:\s+(?:'+INITIAL+r'|'+WORD+r')){1,5}')
PREFIXES = {'the','a','an','director','screenwriter','screenwriters','actor','actress',
            'cinematographer','composer','editor','producer'}


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).replace('’', "'").casefold().split())


def missing_mentions(claim, passage):
    """Conservatively require source-local spelling for multiword capitalized names."""
    context = normalized(passage.text)
    title = normalized(MOVIE_ARTICLES.get(passage.origin.movie_id, '')) if passage.origin else ''
    missing = []
    for match in NAME.finditer(claim):
        # Movie identity is trusted from the registered source, including titles
        # starting with an article. Strip role/article prefixes only afterwards.
        if normalized(match.group()).removesuffix("'s") == title:
            continue
        words = match.group().split()
        while words and words[0].casefold() in PREFIXES:
            words.pop(0)
        if len(words) < 2:
            continue
        mention = ' '.join(words)
        key = normalized(mention)
        if key.endswith("'s"):
            key = key[:-2]
        if key != title and not re.search(r'(?<!\w)'+re.escape(key)+r'(?!\w)',context):
            if mention not in missing:
                missing.append(mention)
    return missing


class FactAssessment(StrictRecord):
    item_id: str = Field(pattern=r'^F[1-3]$')
    missing_mentions: list[str] = Field(max_length=40)
    semantic_decision: Literal['accept','reject','uncertain']
    content: Literal['eligible','plot_in_facts','basic_metadata','uninteresting','duplicate']
    reason: str = Field(min_length=10,max_length=400)


class FactDecision(DraftDecision):
    assessment: FactAssessment | None = None


class FactReview(DraftReview):
    items: list[FactDecision] = Field(max_length=3)


def decision_for(assessment):
    # Missing evidence withholds a claim; it does not establish that it is false.
    return 'uncertain' if assessment.missing_mentions else assessment.semantic_decision


async def review_proposals(client, *, model, proposals, evidence):
    if client.base_url != httpx.URL('http://127.0.0.1:11434') or client.follow_redirects:
        raise ValueError('Use the fixed local Ollama client without redirects')
    if proposals.questions:
        raise ValueError('Background fact review cannot review quiz questions')
    sources = {e.passage_id:e for e in validate_evidence(evidence)}
    checks = check_proposals(proposals,evidence)
    result = await semantic_review(client,model=model,proposals=proposals,evidence=evidence)
    ids = [item.item_id for item in result.items]
    expected = {f'F{i+1}' for i in range(len(proposals.facts))}
    if len(set(ids)) != len(ids) or set(ids) != expected:
        raise ValueError('Exactly one semantic review per background candidate is required')
    decisions = []
    for item in result.items:
        index = int(item.item_id[1:])-1
        if not checks[index]['support_checks_passed']:
            decisions.append(FactDecision(item_id=item.item_id,decision='reject',reason=item.reason))
            continue
        proposal = proposals.facts[index]
        if item.assessment is None:
            raise ValueError('Missing structured fact assessment')
        # Editorial headings are naturally title-cased. The semantic reviewer
        # checks them; this narrow name heuristic applies to the factual body.
        missing = missing_mentions(proposal.text,sources[proposal.passage_id])
        assessment = FactAssessment(item_id=item.item_id,missing_mentions=missing,
                                   semantic_decision=item.decision,
                                   content=item.assessment.content,reason=item.reason)
        reason = ('Names absent from supplied context: '+', '.join(missing))[:400] if missing else item.reason
        decisions.append(FactDecision(item_id=item.item_id,decision=decision_for(assessment),
                                      reason=reason,assessment=assessment))
    return FactReview(items=decisions)
