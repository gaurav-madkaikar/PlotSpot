"""Draft contracts and deterministic checks; none of these publish content."""
import re

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .source_sections import matches_purpose


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceOrigin(StrictRecord):
    movie_id: int = Field(gt=0)
    source_id: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=500)
    revision: str = Field(min_length=1, max_length=100)
    section_title: str = Field(min_length=1, max_length=200)
    section_category: Literal['plot', 'production', 'casting', 'filming', 'music', 'effects', 'other']
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ProposalEvidence(StrictRecord):
    passage_id: str = Field(pattern=r"^P[1-9][0-9]?$", max_length=3)
    purpose: Literal["story", "background"]
    text: str = Field(min_length=20, max_length=600)
    origin: EvidenceOrigin | None = None


class FactProposal(StrictRecord):
    title: str = Field(min_length=5, max_length=120)
    text: str = Field(min_length=20, max_length=450)
    passage_id: str = Field(pattern=r"^P[1-9][0-9]?$", max_length=3)
    evidence_quote: str = Field(min_length=20, max_length=600)


class QuizProposal(StrictRecord):
    question: str = Field(min_length=15, max_length=250)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    passage_id: str = Field(pattern=r"^P[1-9][0-9]?$", max_length=3)
    evidence_quote: str = Field(min_length=20, max_length=600)


class ContentProposals(StrictRecord):
    # Empty lists are valid abstention, not a reason to invent a quota.
    facts: list[FactProposal] = Field(max_length=3)
    questions: list[QuizProposal] = Field(max_length=3)


# These are deliberately narrow, code-owned exclusions for the two public
# product surfaces.  The model still performs the broader semantic judgement,
# but it cannot turn obvious credits/metadata into a story quiz or obvious
# plot/metadata into a behind-the-scenes fact.
NON_STORY_QUIZ = re.compile(
    r'\b(?:actor|actress|cast member|portray(?:s|ed)?|director|filmmaker|producer|'
    r'screenwriter|cinematographer|composer|novella|novel|source material|short story|'
    r'publish(?:ed|ing)|runtime|running time|box[ -]office|academy award|oscar|'
    r'filming|production budget|reviewer|review)\b', re.I)
NON_BACKGROUND_FACT = re.compile(
    r'\b(?:protagonist|antagonist|fictional character|running time|runtime|'
    r'average rating|audience score|production companies?|release date|'
    r'(?:production )?budget|revenue)\b', re.I)
LOW_VALUE_BACKGROUND_FACT = re.compile(
    r'\b(?:hidden star|handled (?:the )?camera work|required (?:critical )?'
    r'(?:praise|kudos|honou?rs)|meticulously captured|served as (?:the )?'
    r'(?:director|producer|cinematographer|composer|editor)|was reviewed at)\b', re.I)


def scope_problem(kind, item):
    """Return a stable scope error for clear product-category violations."""
    if kind == 'question' and NON_STORY_QUIZ.search(item.question):
        return 'outside_story_quiz_scope'
    if kind == 'fact' and NON_BACKGROUND_FACT.search(item.title + ' ' + item.text):
        return 'outside_background_fact_scope'
    if kind == 'fact' and (LOW_VALUE_BACKGROUND_FACT.search(item.title + ' ' + item.text)
            or re.search(r'\bcredit\b', item.title, re.I)
            or re.match(r'^\s*(?:studios|movies|films)\b', item.text, re.I)):
        return 'low_value_background_fact'
    return None


def validate_evidence(evidence):
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
        raise ValueError("Supply one to eight labelled evidence passages")
    records = [ProposalEvidence.model_validate(e.model_dump() if isinstance(e, ProposalEvidence) else e) for e in evidence]
    if len({e.passage_id for e in records}) != len(records):
        raise ValueError("Passage IDs must be unique")
    return records


def check_proposals(proposals, evidence):
    """Report necessary support checks, not semantic truth or publication approval."""
    proposals = ContentProposals.model_validate(proposals.model_dump())
    sources = {e.passage_id: e for e in validate_evidence(evidence)}
    findings = []
    for kind, items, purpose in [('fact', proposals.facts, 'background'), ('question', proposals.questions, 'story')]:
        previous = set()
        for index, item in enumerate(items):
            problems = []
            source = sources.get(item.passage_id)
            if source is None:
                problems.append('unknown_passage')
            elif source.purpose != purpose:
                problems.append('wrong_evidence_purpose')
            elif source.origin and not matches_purpose(source.origin.section_category, purpose):
                problems.append('wrong_source_section')
            elif item.evidence_quote not in source.text:
                problems.append('quote_not_in_source')
            wording = item.text if kind == 'fact' else item.question
            normalized = ' '.join(re.findall(r'\w+', wording.casefold()))
            if normalized in previous:
                problems.append('duplicate_text')
            previous.add(normalized)
            if kind == 'question':
                options = [' '.join(re.findall(r'\w+', option.casefold())) for option in item.options]
                if any(not option.strip() or len(option) > 150 for option in item.options) or len(set(options)) != 4:
                    problems.append('invalid_options')
            scope = scope_problem(kind, item)
            if scope:
                problems.append(scope)
            findings.append({'kind': kind, 'index': index, 'passage_id': item.passage_id,
                             'support_checks_passed': not problems, 'problems': problems,
                             'semantic_review_required': True})
    return findings
