"""Integration boundaries: acquisition, scope, provenance, review and cancellation."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import pytest
from movie_companion.evidence_store import SourceDocument
from movie_companion.source_sections import SourceSection
from movie_companion.movie_source_corpus import CorpusResult
from movie_companion.movie_questions import MovieQuestion,QuestionCitation
from movie_companion.retrieval_learning import EmbeddedPassage
from movie_companion.grounding_learning import GroundedAnswer
from movie_companion.movie_web_sources import make_web_source
from movie_companion.public_web import WebRead
from movie_companion.web_corpus_store import WebCorpusStore
import movie_companion.multi_source_pipeline as flow
import movie_companion.research_workflow as research
import movie_companion.source_corroboration as corroboration
from test_multi_source_corpus import MOVIE,article

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setenv('PLOTSPOT_WEB_CORPUS_DB',str(tmp_path/'web.db'))
    registry=WebCorpusStore()
    source=make_web_source(MOVIE,WebRead('https://movie.example/story',article(),'text/html'),purpose='story')
    registry.remember(source,'web')
    text='An early draft describes an unverified alternate ending for this movie.'
    script=SourceDocument('imsdb-157336-part-0',157336,text,'Unverified early draft',
        'https://imsdb.com/scripts/Interstellar.html','imsdb-'+'a'*64,'spoiler',
        (SourceSection(0,len(text),'Draft scene','plot'),))
    registry.remember(script,'script')
    passage=lambda s:EmbeddedPassage(s.source_id,157336,s.text[:500],[1.,.5],'nomic-embed-text:v1.5',s.source_label,'unknown')
    class Store:
        def load_snapshot(self,s,**kw):return [passage(s)]
    class Corpus:
        async def collect(self,movie,**kw):
            assert movie==MOVIE
            return CorpusResult((source,script),{'degraded':True,'source_count':2})
    async def unavailable(mid):raise OSError('Wiki unavailable')
    async def identity(mid):return MOVIE
    async def ingest(*args,**kw):pass
    async def reader():return SimpleNamespace(documents=[])
    monkeypatch.setattr(flow,'ingest_source',ingest)
    monkeypatch.setattr(flow,'source_loaders',lambda *a,**kw:(None,reader))
    monkeypatch.setattr(flow,'published_background_sources',lambda mid:[])
    service=SimpleNamespace(identity_loader=identity,load_evidence=unavailable,corpus=Corpus(),
        store=Store(),ollama=None,embedding_model='nomic-embed-text:v1.5',chat_model='llama3.2:3b',
        chunk_settings={'max_chars':600,'overlap_chars':100},source_traces={})
    return service,source,script

@pytest.mark.parametrize('verdict',['supported','unsupported','uncertain'])
def test_web_answer_with_wiki_outage_requires_second_publisher(prepared,monkeypatch,verdict):
    service,source,script=prepared
    async def pipeline(client,**kw):
        assert all(p.movie_id==157336 for p in kw['passages'])
        return GroundedAnswer('answered','An authored supported answer.',(source.source_id,))
    async def review(client,**kw):
        assert kw['quotes'] and all('early draft' not in quote for quote in kw['quotes'])
        return SimpleNamespace(verdict=verdict,evidence_quotes=(kw['quotes'][0],) if verdict=='supported' else ())
    monkeypatch.setattr(flow,'answer_movie_question',pipeline);monkeypatch.setattr(corroboration,'review_support',review)
    reply=asyncio.run(flow.answer_multi_source(service,157336,MovieQuestion(question='What happens?',allow_spoilers=True)))
    assert reply.status=='insufficient_evidence' and reply.source_coverage['degraded']
    assert not reply.citations


def test_answer_requires_each_of_two_publishers_to_support_complete_answer(prepared,monkeypatch):
    service,source,script=prepared
    second=replace(source,source_id='web-second',source_ref='https://second.example/story')
    WebCorpusStore().remember(second,'web')
    original_collect=service.corpus.collect
    async def collect(movie,**kw):
        result=await original_collect(movie,**kw)
        return CorpusResult((source,second,script),{'degraded':False,'source_count':3})
    service.corpus.collect=collect
    async def pipeline(client,**kw):
        return GroundedAnswer('answered','Cooper follows dust coordinates to NASA.',(source.source_id,second.source_id))
    async def review(client,**kw):
        return SimpleNamespace(verdict='supported',evidence_quotes=(kw['quotes'][0],))
    monkeypatch.setattr(flow,'answer_movie_question',pipeline);monkeypatch.setattr(corroboration,'review_support',review)
    reply=asyncio.run(flow.answer_multi_source(service,157336,MovieQuestion(question='Where do the coordinates lead?',allow_spoilers=True)))
    assert reply.status=='answered'
    assert reply.source_coverage['answer_publishers']==['movie.example','second.example']
    assert {citation.source_ref for citation in reply.citations}=={source.source_ref,second.source_ref}


def test_script_only_answer_cannot_claim_released_film_authority(prepared,monkeypatch):
    service,source,script=prepared
    async def pipeline(*a,**kw):return GroundedAnswer('answered','Unverified alternate ending.',(script.source_id,))
    async def review(*a,**kw):raise AssertionError('No released evidence to review')
    monkeypatch.setattr(flow,'answer_movie_question',pipeline);monkeypatch.setattr(flow,'review_support',review)
    reply=asyncio.run(flow.answer_multi_source(service,157336,MovieQuestion(question='How does it end?',allow_spoilers=True)))
    assert reply.status=='insufficient_evidence' and not reply.citations
    with pytest.raises(ValueError):QuestionCitation(passage_id='x',source_ref=script.source_ref,
        source_label=script.source_label,revision=script.revision,excerpt=script.text)


def test_invented_cross_source_citation_is_rejected(prepared,monkeypatch):
    service,_,_=prepared
    async def pipeline(*a,**kw):return GroundedAnswer('answered','Invented.',('different_movie',))
    monkeypatch.setattr(flow,'answer_movie_question',pipeline)
    with pytest.raises(ValueError):asyncio.run(flow.answer_multi_source(service,157336,MovieQuestion(question='Question',allow_spoilers=True)))


def test_cancelled_request_joins_acquisition_parent(prepared):
    service,_,_=prepared
    async def run():
        started=asyncio.Event();joined=asyncio.Event()
        async def collect(*a,**kw):
            started.set()
            try:await asyncio.Event().wait()
            finally:joined.set()
        async def wiki(mid):await started.wait();await asyncio.Event().wait()
        service.corpus.collect=collect;service.load_evidence=wiki
        task=asyncio.create_task(flow.source_bundle(service,157336));await started.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert joined.is_set()
    asyncio.run(run())


def test_wrong_movie_identity_is_rejected_before_source_io(prepared):
    service,_,_=prepared
    async def wrong(mid):return replace(MOVIE,movie_id=155)
    service.identity_loader=wrong
    with pytest.raises(ValueError,match='identity mismatch'):asyncio.run(flow.source_bundle(service,157336))


def test_research_plan_uses_multiple_publishers_and_never_scripts_as_authority(prepared,monkeypatch):
    service,source,script=prepared
    second=replace(source,source_id='web-second',source_ref='https://second.example/story')
    third=replace(source,source_id='web-third',source_ref='https://third.example/story')
    store=WebCorpusStore();store.remember(second,'web');store.remember(third,'web')
    async def retrieved(*a,source,**kw):
        assert source.source_id!=script.source_id
        return SimpleNamespace(batches=[[SimpleNamespace(purpose='story',model_dump=lambda:{'purpose':'story'})]]*5)
    monkeypatch.setattr(research,'retrieve_draft_evidence',retrieved)
    documents=[SimpleNamespace(source=s,article=None) for s in (source,second,third,script)]
    tasks=asyncio.run(research.build_plan(None,documents=documents,store=None,targets={'facts':0,'questions':10}))
    assert [t['source_id'] for t in tasks[:3]]==[source.source_id,second.source_id,third.source_id]
    assert all(t['source_id']!=script.source_id for t in tasks)


def test_hierarchical_pool_keeps_query_matches_from_each_source_under_existing_budget(prepared,monkeypatch):
    import movie_companion.embedding_learning as embeddings
    service,source,_=prepared
    async def embed(*a,**kw):return [[1.,.5]]
    monkeypatch.setattr(embeddings,'embed_texts',embed)
    passages=[];mapping={}
    for index in range(3):
        s=replace(source,source_id=f'source-{index}')
        for row in range(180):
            text='NASA coordinates locate the facility.' if row==170 else 'Unrelated film discussion.'
            p=EmbeddedPassage(f'p-{index}-{row}',157336,text,[1.,.5],service.embedding_model,s.source_label,'unknown')
            passages.append(p);mapping[p.passage_id]=s
    bounded=asyncio.run(flow.bounded_pool(service,passages,mapping,'Where do the NASA coordinates lead?',157336))
    assert len(bounded)<=400 and len({mapping[p.passage_id].source_id for p in bounded})==3
    assert all(f'p-{index}-170' in {p.passage_id for p in bounded} for index in range(3))


def test_independent_publication_gate_rejects_missing_and_forged_reference_proof(prepared):
    from movie_companion.research_checkpoint import independent_support
    service,web,_=prepared
    text='The coordinates lead Cooper and Murph to a hidden NASA facility.'
    wiki=SourceDocument('enwiki-reference',157336,text,'English Wikipedia contributors: Interstellar',
        'https://en.wikipedia.org/w/index.php?oldid=123','enwiki-123-sections-v3-body','unknown',
        (SourceSection(0,len(text),'Plot','plot'),))
    sources={web.source_id:web,wiki.source_id:wiki}
    assert not independent_support(None,sources,web)
    assert not independent_support({'status':'unsupported'},sources,web)
    proof={'status':'supported','source_id':wiki.source_id,'revision':wiki.revision,'evidence':[text],
        'review':{'verdict':'supported','reason':'Exact location stated.','evidence_answer':'A hidden NASA facility.','evidence_quotes':[text]}}
    assert independent_support(proof,sources,web)
    second=replace(wiki,source_id='second-reference',source_label='Independent movie synopsis',
        source_ref='https://example.org/interstellar-story',revision='web-second-v1')
    sources[second.source_id]=second
    second_proof={**proof,'source_id':second.source_id,'revision':second.revision}
    assert independent_support(second_proof,sources,web)
    for bad in [{**proof,'source_id':web.source_id},{**proof,'revision':'changed'},{**proof,'evidence':['Invented quote that is not in the reference source.']}]:
        with pytest.raises(ValueError):independent_support(bad,sources,web)


def test_quiz_corroboration_ranks_relevant_story_source_before_background_pages(prepared):
    _, original, script = prepared
    background_text='The production used practical lighting and handheld cameras.'
    story_text='Robert Paulsen joins the cancer support group before Project Mayhem begins.'
    background = replace(original, source_id='background',
        source_ref='https://background.example/production',
        text=background_text,
        sections=(SourceSection(0,len(background_text),'Production','production'),))
    story = replace(original, source_id='story', source_ref='https://story.example/plot',
        text=story_text,
        sections=(SourceSection(0,len(story_text),'Plot','plot'),))
    irrelevant = [replace(background,source_id=f'background-{index}',
        source_ref=f'https://background-{index}.example/production') for index in range(5)]
    documents=[SimpleNamespace(source=item) for item in (script,*irrelevant,story)]

    ranked=corroboration.ranked_independent_sources(source=original,documents=documents,
        question='Who joins the cancer support group?',answer='Robert Paulsen')

    assert ranked[0].source_id=='story'
    assert script.source_id not in {item.source_id for item in ranked}
