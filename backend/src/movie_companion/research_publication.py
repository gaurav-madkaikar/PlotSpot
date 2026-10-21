"""Explicit reviewed selections; no HTTP route or model can call this publisher."""
from dataclasses import asdict
import json
from pathlib import Path
from typing import Literal

from pydantic import Field,model_validator

from .background_articles import load_article,DEFAULT_CACHE
from .content_proposals import StrictRecord
from .content_store import ContentStore
from .evidence_store import SourceDocument
from .movie_facts import MovieFact,MovieFacts
from .movie_quiz import MovieQuiz,QuizItem
from .movie_questions import QuestionCitation
from .research_checkpoint import POLICY,derive,digest,bank_identity,source_map
from .research_jobs import load_bank


class ReviewedSelection(StrictRecord):
    movie_id: int = Field(gt=0)
    job_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    report_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    item_ids: list[str] = Field(min_length=1,max_length=15)
    reviewer: str = Field(min_length=3,max_length=100)
    review_kind: Literal['human_source_review','assistant_source_review']
    reviewed_sources_and_novelty: Literal[True]

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.item_ids))!=len(self.item_ids):raise ValueError('Review item IDs must be unique')
        if not self.reviewer.strip():raise ValueError('Identify the reviewer')
        return self


def verify_cached_sources(report,*,sources,article_cache=DEFAULT_CACHE):
    docs=source_map(report['movie_id'],report['sources'])
    for expected in docs.values():
        from .web_corpus_store import registered_source_match,registered_source
        if registered_source_match(expected):actual=registered_source(expected)
        elif expected.revision.startswith('enwiki-'):
            path=Path(sources)/f"{report['movie_id']}.json"
            if not path.is_file() or path.stat().st_size>1_000_000:raise ValueError('Reviewed Wikipedia snapshot is unavailable')
            actual=SourceDocument(**json.loads(path.read_text()))
        else:actual=load_article(expected.source_id,cache_dir=article_cache).source
        if digest(asdict(actual))!=digest(asdict(expected)):raise ValueError('Source changed since preparation/review')
    return docs


def compile_selection(report,saved,selection):
    facts,questions,candidates=derive(report,saved)
    by_id={c['id']:c for c in candidates}
    if any(cid not in by_id or not by_id[cid]['retained'] for cid in selection.item_ids):
        raise ValueError('Only validated retained candidates can be selected')
    sources=source_map(report['movie_id'],report['sources'])
    quiz=MovieQuiz(status='ready',message='Saved story collection.',items=[]) if saved is None else saved['quiz'].model_copy(deep=True)
    fact_bank=MovieFacts(status='ready',message='Saved production background.',items=[]) if saved is None else saved['facts'].model_copy(deep=True)
    scored=[q for q in quiz.items if q.kind!='interpretation'];readings=[q for q in quiz.items if q.kind=='interpretation']
    for cid in selection.item_ids:
        candidate=by_id[cid];proposal=candidate['proposal'];source=sources[candidate['source_id']]
        quote=proposal['evidence_quote']
        citation=QuestionCitation(passage_id=digest({'source':source.revision,'origin':candidate['origin'],'quote':quote})[:32],
            source_label=source.source_label,source_ref=source.source_ref,revision=source.revision,excerpt=quote,
            source_kind='web' if source.revision.startswith('web-') else 'reviewed',source_verified=source.revision.startswith('web-'))
        item_id='research-'+selection.job_id[:12]+'-'+cid
        if candidate['kind']=='question':
            if target_id:=candidate.get('corroborates'):
                target=next((item for item in scored if item.id==target_id),None)
                if target is None or len(target.citations)>=3 or any(c.revision==citation.revision for c in target.citations):
                    raise ValueError('Invalid quiz corroboration target')
                target.citations.append(citation)
            else:
                scored.append(QuizItem(id=item_id,origin='generated',kind='plot',question=proposal['question'],
                    options=proposal['options'],correct_index=proposal['correct_index'],explanation=quote,citations=[citation]))
        else:
            fact_bank.items.append(MovieFact(id=item_id,title=proposal['title'],text=proposal['text'],citations=[citation]))
    quiz.items=scored+readings
    if len(fact_bank.items)>12 or len(quiz.items)>40:raise ValueError('Shared collection capacity reached')
    manifest={c.revision:c.source_ref for item in [*quiz.items,*fact_bank.items] for c in item.citations}
    source_revision=saved['source_revision'] if saved else next((s.revision for s in sources.values() if s.revision.startswith('enwiki-')),next(iter(sources.values())).revision)
    ContentStore.validate(quiz,fact_bank)
    ContentStore.validate_manifest(quiz,fact_bank,source_revision,manifest)
    if report.get('coverage_policy'):
        from .source_coverage import POLICY as COVERAGE,require_content_coverage
        if report['coverage_policy']!=COVERAGE:raise ValueError('Unknown publication coverage policy')
        require_content_coverage(quiz,fact_bank)
    return quiz,fact_bank,source_revision,manifest


def publish_selection(*,jobs,bank,selection,sources,article_cache=DEFAULT_CACHE):
    selection=ReviewedSelection.model_validate(selection.model_dump() if isinstance(selection,ReviewedSelection) else selection)
    selection_sha=digest(selection.model_dump())
    receipt=bank.receipt(selection.job_id)
    if receipt is not None:
        if receipt['selection_sha256']!=selection_sha or receipt['movie_id']!=selection.movie_id:
            raise ValueError('Published job selection conflicts')
        jobs.mark_published(selection.movie_id,selection.job_id,selection.report_sha256,receipt)
        return {**receipt,'replayed':True}
    record=jobs.latest(selection.movie_id)
    if record is None or record['id']!=selection.job_id or record['state'] not in ('needs_review','incomplete'):
        raise ValueError('Select a completed, reviewable job')
    report=record.get('report')
    if (not isinstance(report,dict) or report.get('workflow')!=POLICY or report.get('reused')
            or report.get('movie_id')!=selection.movie_id
            or report.get('publication_approved') is not False or digest(report)!=selection.report_sha256):
        raise ValueError('Report changed or is not an unpublished research job')
    saved=bank.load(selection.movie_id)
    if bank_identity(saved)!=report['bank_sha256']:raise ValueError('Saved collection changed since preparation')
    verify_cached_sources(report,sources=sources,article_cache=article_cache)
    quiz,facts,revision,manifest=compile_selection(report,saved,selection)
    receipt=bank.publish_with_receipt(selection.movie_id,job_id=selection.job_id,selection_sha256=selection_sha,
        report_sha256=selection.report_sha256,reviewer=selection.reviewer,review_kind=selection.review_kind,
        version='research-'+selection.job_id[:12],source_revision=revision,quiz=quiz,facts=facts,
        expected_prepared_at=saved['prepared_at'] if saved else None,source_manifest=manifest)
    # A crash here is recoverable: the next identical selection sees the content
    # receipt first and reconciles the job without publishing again.
    jobs.mark_published(selection.movie_id,selection.job_id,selection.report_sha256,receipt)
    return receipt
