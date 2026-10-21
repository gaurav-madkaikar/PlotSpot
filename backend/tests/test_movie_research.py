import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from movie_companion.background_registry import ARTICLES
from movie_companion.evidence_store import SourceDocument
from movie_companion.external_sources import ArticleSnapshot
from movie_companion.movie_research import (
    ReadFailure, ResearchDocument, ResearchLoad, research_movie, source_loaders,
)
from movie_companion.source_sections import SourceSection


def story_document():
    text = 'Louise Banks learns that her apparent memories are visions of the future.'
    return ResearchDocument(SourceDocument('wiki_329865', 329865, text,
        'English Wikipedia contributors: Arrival (film)',
        'https://en.wikipedia.org/w/index.php?oldid=123',
        'enwiki-123-sections-v3-body', sections=(SourceSection(0,len(text),'Plot','plot'),)))


def background_document(identifier='time-arrival'):
    record = ARTICLES[identifier]
    text = 'The production team built a practical chamber instead of using a green screen.'
    source = SourceDocument(record.id,329865,text,record.publisher+' · '+record.headline,
        record.url,'article-fixture',sections=(SourceSection(0,len(text),'Background 1','filming'),))
    snapshot = ArticleSnapshot(source,record.publisher,record.authors,record.published_at,
                               '2026-10-12T00:00:00+00:00','a'*64)
    return ResearchDocument(source,snapshot)


async def good_story():
    return ResearchLoad((story_document(),))


async def good_background():
    return ResearchLoad((background_document(),))


def run(story=good_story, background=good_background, **options):
    return asyncio.run(research_movie(movie_id=329865,story_loader=story,
                                      background_loader=background,**options))


@pytest.mark.parametrize('mode',['parallel','sequential'])
def test_stable_order_provenance_and_no_model_tools(mode):
    result = run(mode=mode)
    assert [b.purpose for b in result.branches] == ['story','background']
    assert [b.status for b in result.branches] == ['complete','complete']
    trace = result.trace()
    assert trace['model_calls'] == 0 and trace['published'] is False
    assert trace['branches'][0]['sources'][0]['revision'] == 'enwiki-123-sections-v3-body'
    assert len(trace['branches'][0]['sources'][0]['sha256']) == 64


def test_parallel_branches_start_before_either_finishes():
    async def call():
        entered = set()
        ready = asyncio.Event()
        async def loader(purpose):
            entered.add(purpose)
            if len(entered)==2: ready.set()
            await ready.wait()
            return await (good_story() if purpose=='story' else good_background())
        return await research_movie(movie_id=329865,story_loader=lambda:loader('story'),
            background_loader=lambda:loader('background'),branch_seconds=.5,deadline_seconds=1)
    result = asyncio.run(call())
    assert [e['event'] for e in result.events[:2]] == ['started','started']
    assert all(b.status=='complete' for b in result.branches)


def test_sequential_baseline_does_not_overlap_loaders():
    events = []
    async def story():
        events.append('story');return await good_story()
    async def background():
        assert events==['story'];events.append('background');return await good_background()
    result = run(story,background,mode='sequential')
    assert [e['purpose'] for e in result.events]==['story','story','background','background']


@pytest.mark.parametrize('mode',['parallel','sequential'])
@pytest.mark.parametrize('error',[ValueError('secret body'),httpx.HTTPError('private token')])
def test_expected_failure_retains_other_branch_without_error_body(mode,error):
    async def broken():raise error
    result = run(background=broken,mode=mode)
    assert result.branches[0].status=='complete'
    assert result.branches[1].status=='failed'
    assert 'secret' not in json.dumps(result.trace()) and 'private token' not in json.dumps(result.trace())


def test_one_article_failure_preserves_other_article():
    async def partial():
        return ResearchLoad((background_document('bfi-arrival'),),
                            (ReadFailure('time-arrival','HTTPError'),))
    result = run(background=partial)
    assert result.branches[1].status=='partial'
    assert result.branches[1].documents[0].source.source_id=='bfi-arrival'


@pytest.mark.parametrize('mode',['parallel','sequential'])
def test_branch_timeout_joins_and_retains_story(mode):
    ended = []
    async def hung():
        try: await asyncio.Event().wait()
        finally: ended.append('joined')
    result = run(background=hung,mode=mode,branch_seconds=.02,deadline_seconds=.5)
    assert result.branches[0].status=='complete'
    assert result.branches[1].status=='timed_out' and ended==['joined']


def test_global_timeout_preserves_completed_branch_and_joins_other():
    ended=[]
    async def hung():
        try: await asyncio.Event().wait()
        finally: ended.append('joined')
    result=run(background=hung,branch_seconds=1,deadline_seconds=.02)
    assert result.branches[0].status=='complete'
    assert result.branches[1].errors[0].source_id=='workflow' and ended==['joined']


def test_caller_cancel_propagates_after_joining_both_children():
    async def call():
        ready=asyncio.Event();entered=[];ended=[]
        async def hung():
            entered.append(1)
            if len(entered)==2:ready.set()
            try:await asyncio.Event().wait()
            finally:ended.append(1)
        task=asyncio.create_task(research_movie(movie_id=329865,story_loader=hung,background_loader=hung))
        await ready.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert len(ended)==2
    asyncio.run(call())


def test_programming_failure_propagates_and_cancels_sibling():
    async def call():
        ready=asyncio.Event();ended=[]
        async def broken():await ready.wait();raise RuntimeError('programming bug')
        async def hung():
            ready.set()
            try:await asyncio.Event().wait()
            finally:ended.append(1)
        with pytest.raises(ExceptionGroup) as caught:
            await research_movie(movie_id=329865,story_loader=broken,background_loader=hung)
        assert isinstance(caught.value.exceptions[0],RuntimeError) and ended==[1]
    asyncio.run(call())


@pytest.mark.parametrize('corruption',['wrong_movie','wrong_url','plot_in_background','repeated_source'])
def test_bad_background_output_is_rejected_before_model_work(corruption):
    document=background_document()
    if corruption=='repeated_source':documents=(document,document)
    else:
        source=replace(document.source,**({'movie_id':155} if corruption=='wrong_movie' else
            {'source_ref':'https://evil.example/'} if corruption=='wrong_url' else
            {'sections':(SourceSection(0,len(document.source.text),'Plot','plot'),)}))
        documents=(ResearchDocument(source,replace(document.article,source=source)),)
    async def bad():return ResearchLoad(documents)
    assert run(background=bad).branches[1].status=='failed'


@pytest.mark.parametrize('options',[{'mode':'random'},{'branch_seconds':True},
                                  {'deadline_seconds':121},{'branch_seconds':float('nan')}])
def test_invalid_budgets_fail_before_loader_calls(options):
    async def bad():raise AssertionError('must not run')
    with pytest.raises(ValueError):run(bad,bad,**options)


def test_cached_adapters_preserve_partial_articles_and_never_use_network(tmp_path,monkeypatch):
    from dataclasses import asdict
    from movie_companion import background_articles
    (tmp_path/'329865.json').write_text(json.dumps(asdict(story_document().source)))
    def load(identifier,**kwargs):
        if identifier=='time-arrival':raise ValueError('missing cache')
        return background_document(identifier).article
    monkeypatch.setattr(background_articles,'load_article',load)
    story,background=source_loaders(329865,sources=tmp_path,article_cache=tmp_path)
    result=run(story,background)
    assert [b.status for b in result.branches]==['complete','partial']


def test_movie_without_registered_articles_reports_unavailable(tmp_path):
    story,background=source_loaders(155,sources=tmp_path)
    result=asyncio.run(background())
    assert result==ResearchLoad()
