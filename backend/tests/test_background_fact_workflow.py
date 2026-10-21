import asyncio
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

import movie_companion.background_fact_workflow as flow
from movie_companion.background_articles import parse_article
from movie_companion.background_registry import ARTICLES
from movie_companion.content_proposals import EvidenceOrigin, ProposalEvidence
from movie_companion.content_store import ContentStore
from movie_companion.evidence_store import SourceDocument
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit
from movie_companion.source_sections import SourceSection, source_chunks
from test_background_articles import DATE, html_fixture
from test_content_store import fixture_collection


def publication_fixture(tmp_path,monkeypatch):
    source,(quiz,facts)=fixture_collection()
    store=ContentStore(tmp_path/'content.db')
    store.publish(329865,version='v1',source_revision=source.revision,quiz=quiz,facts=facts)
    saved=store.load(329865)
    snapshots={key:parse_article(html_fixture(key),identifier=key,retrieved_at=DATE) for key in ARTICLES}
    monkeypatch.setattr(flow,'load_article',lambda identifier,**kw:snapshots[identifier])
    snapshot=snapshots['time-arrival'];s=snapshot.source;section=s.sections[0]
    passage=s.text[section.start:section.end]
    quote='Authored background: the crew built a reusable light rig.'
    report={'policy':flow.POLICY,'implementation_sha256':flow.fingerprint(),
        'model':flow.MODEL,'model_digest':flow.DIGESTS[flow.MODEL],
        'embedding_model':flow.EMBEDDING,'embedding_digest':flow.DIGESTS[flow.EMBEDDING],
        'published':False,'index_only':False,'errors':[],'movie_id':329865,
        'saved_prepared_at':saved['prepared_at'],
        'sources':[{'id':identifier,'revision':snapshot.source.revision,
                    'content_sha256':snapshot.content_sha256,
                    'text_sha256':hashlib.sha256(snapshot.source.text.encode()).hexdigest(),
                    'source_ref':snapshot.source.source_ref} for identifier,snapshot in snapshots.items()],
        'candidates':[{'id':'time-arrival:F1','source_id':s.source_id,
            'proposal':{'title':'A reusable lighting rig','text':'The production crew built a lighting rig designed for reuse.',
                        'passage_id':'P1','evidence_quote':quote},
            'origin':EvidenceOrigin(movie_id=329865,source_id=s.source_id,source_ref=s.source_ref,
                revision=s.revision,section_title=section.title,section_category=section.category,
                start=section.start,end=section.end).model_dump(),
            'evidence_sha256':hashlib.sha256(passage.encode()).hexdigest(),
            'critic_decision':'accept','critic_assessment':{'item_id':'F1','missing_mentions':[],'semantic_decision':'accept','content':'eligible','reason':'The fixture evidence supports the whole production claim.'},'eligible_for_review':True}]}
    report_path=tmp_path/'report.json';selection_path=tmp_path/'selection.json'
    def write():
        report_path.write_text(json.dumps(report))
        selection_path.write_text(json.dumps({'report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
            'item_ids':['time-arrival:F1']}))
    write()
    return store,saved,report,report_path,selection_path,write,snapshots


def test_inspected_publication_preserves_quiz_old_facts_and_manifest(tmp_path,monkeypatch):
    store,saved,report,path,selection,write,snapshots=publication_fixture(tmp_path,monkeypatch)
    result=flow.publish_reviewed(store,report_path=path,selection_path=selection)
    current=ContentStore(store.path).load(329865)
    assert result['added']==1 and result['quiz_preserved']
    assert current['quiz']==saved['quiz'] and current['facts'].items[:5]==saved['facts'].items
    assert current['facts'].reading_sources[0].kind=='interview'
    assert current['facts'].items[-1].citations[0].source_ref==ARTICLES['time-arrival'].url
    with pytest.raises(ValueError):flow.publish_reviewed(store,report_path=path,selection_path=selection)
    assert store.load(329865)==current


@pytest.mark.parametrize('failure',['report_hash','fingerprint','movie','published','index_only','error',
    'rejected','ineligible','unknown_id','unknown_source','origin_movie','origin_url','quote',
    'snapshot_revision','evidence_hash','model','duplicate_ids','duplicate_candidate','stale','capacity','copied'])
def test_invalid_selection_and_evidence_never_replace_saved_content(tmp_path,monkeypatch,failure):
    store,saved,r,path,selection,write,snapshots=publication_fixture(tmp_path,monkeypatch)
    c=r['candidates'][0]
    if failure=='fingerprint':r['implementation_sha256']='0'*64
    if failure=='movie':r['movie_id']=27205
    if failure=='published':r['published']=True
    if failure=='index_only':r['index_only']=True
    if failure=='error':r['errors']=['Failure']
    if failure=='rejected':c['critic_decision']='reject'
    if failure=='ineligible':c['eligible_for_review']=False
    if failure=='unknown_source':c['source_id']='unreviewed'
    if failure=='origin_movie':c['origin']['movie_id']=157336
    if failure=='origin_url':c['origin']['source_ref']='http://127.0.0.1/private'
    if failure=='quote':c['proposal']['evidence_quote']='A fabricated quote absent from the source.'
    if failure=='snapshot_revision':r['sources'][0]['revision']='changed'
    if failure=='evidence_hash':c['evidence_sha256']='0'*64
    if failure=='model':r['model_digest']='0'*64
    if failure=='duplicate_candidate':r['candidates'].append(c)
    if failure=='stale':r['saved_prepared_at']='yesterday'
    if failure=='copied':
        snapshot=snapshots['time-arrival'];section=snapshot.source.sections[0]
        quote=snapshot.source.text[section.start:section.end].strip()
        c['proposal']['text']=quote;c['proposal']['evidence_quote']=quote
    if failure=='capacity':
        facts=saved['facts'].model_copy(deep=True)
        facts.items.extend(facts.items[0].model_copy(update={'id':f'extra{i}','text':f'Extra authored background {i}.'}) for i in range(7))
        store.publish(329865,version='v2',source_revision=saved['source_revision'],quiz=saved['quiz'],facts=facts)
        saved=store.load(329865);r['saved_prepared_at']=saved['prepared_at']
    write()
    if failure=='report_hash':path.write_text(path.read_text()+' ')
    if failure in ('unknown_id','duplicate_ids'):
        data=json.loads(selection.read_text());data['item_ids']=['unknown'] if failure=='unknown_id' else ['time-arrival:F1']*2
        selection.write_text(json.dumps(data))
    with pytest.raises(ValueError):flow.publish_reviewed(store,report_path=path,selection_path=selection)
    assert store.load(329865)==saved


def test_known_sentence_id_attaches_exact_typographic_quote(monkeypatch):
    text='The cinematographer’s lighting rig used soft illumination rather than harsh lamps.'
    origin=EvidenceOrigin(movie_id=329865,source_id='time-arrival',source_ref=ARTICLES['time-arrival'].url,
        revision='v1',section_title='Production',section_category='filming',start=0,end=len(text))
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=text,origin=origin)]
    async def raw(client,**kw):
        assert kw['response_schema']['$defs']['ArticleFactSeed']['properties']['support_id']['enum']==['S1']
        assert 'Existing' in kw['prompt'] and 'no tools' in kw['prompt']
        return json.dumps({'facts':[{'title':'Soft light on set','text':'The rig gave the production a softer source of illumination.','support_id':'S1'}]})
    monkeypatch.setattr(flow,'chat_once',raw)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            result=await flow.propose_article_facts(client,evidence,['Existing fact'])
            assert result.facts[0].evidence_quote==text and '’' in result.facts[0].evidence_quote
    asyncio.run(run())


@pytest.mark.parametrize('reply',[{'facts':[{'title':'Authored title','text':'Authored twenty character claim.','support_id':'S99'}]},
    {'facts':[{'title':'Authored title','text':'Authored twenty character claim.','support_id':'S1','source_url':'http://localhost/private'}]},
    {'facts':[],'questions':[]}])
def test_writer_cannot_create_citations_or_change_branch(monkeypatch,reply):
    text='The crew built a practical lighting rig for the film.'
    origin=EvidenceOrigin(movie_id=329865,source_id='time-arrival',source_ref=ARTICLES['time-arrival'].url,
        revision='v1',section_title='Production',section_category='filming',start=0,end=len(text))
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=text,origin=origin)]
    async def raw(*a,**kw):return json.dumps(reply)
    monkeypatch.setattr(flow,'chat_once',raw)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            with pytest.raises(ValueError):await flow.propose_article_facts(client,evidence,[])
    asyncio.run(run())


def test_inspection_rejects_nonlocal_clients_without_requests():
    def forbidden(request):pytest.fail('No external model request allowed')
    async def run():
        async with httpx.AsyncClient(base_url='https://evil.example',transport=httpx.MockTransport(forbidden)) as client:
            with pytest.raises(ValueError):await flow.inspect_facts(client,store=None,saved=None,movie_id=329865,snapshots=[])
    asyncio.run(run())


def test_retrieval_trims_partial_window_edges_to_actual_complete_sentences(monkeypatch):
    text=' '.join(f'Authored sentence {i} explains a carefully chosen production lighting technique.' for i in range(14))
    section=SourceSection(0,len(text),'Production','filming')
    source=SourceDocument('time-arrival',329865,text,'TIME fixture',ARTICLES['time-arrival'].url,'v1','unknown',(section,))
    chunks=source_chunks(source,max_chars=600,overlap_chars=100)
    passages=[EmbeddedPassage(str(i),329865,c.text,[1.,0.],flow.EMBEDDING,'TIME fixture',
        section_title='Production',section_category='filming') for i,c in enumerate(chunks)]
    async def ingest(*a,**kw):return 'cached'
    async def embed(*a,**kw):return [[1.,0.]]
    monkeypatch.setattr(flow,'ingest_source',ingest);monkeypatch.setattr(flow,'embed_texts',embed)
    monkeypatch.setattr(flow,'retrieve_passages',lambda *a,**kw:[RetrievalHit(passages[1],.9)])
    store=SimpleNamespace(load_snapshot=lambda *a,**kw:passages)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            evidence,trace=await flow.article_evidence(client,store,SimpleNamespace(source=source))
            assert evidence[0].text.startswith('Authored sentence') and evidence[0].text.endswith('.')
            origin=evidence[0].origin
            assert source.text[origin.start:origin.end]==evidence[0].text
            assert origin.end<chunks[1].end and len(evidence[0].text)<=600
            assert trace['hits'][0]['preceding_context_added'] is True
            assert origin.start<chunks[1].start
    asyncio.run(run())


def test_concurrent_write_during_publication_cannot_append_stale_facts(tmp_path,monkeypatch):
    store,saved,r,path,selection,write,snapshots=publication_fixture(tmp_path,monkeypatch)
    original_publish=store.publish
    def raced(movie_id,**kwargs):
        original_publish(movie_id,version='concurrent',source_revision=saved['source_revision'],
                         quiz=saved['quiz'],facts=saved['facts'])
        return original_publish(movie_id,**kwargs)
    monkeypatch.setattr(store,'publish',raced)
    with pytest.raises(ValueError,match='changed during generation'):
        flow.publish_reviewed(store,report_path=path,selection_path=selection)
    after=store.load(329865)
    assert after['version']=='concurrent' and after['quiz']==saved['quiz'] and after['facts']==saved['facts']


def test_personal_initial_support_keeps_full_names_and_rejects_clipped_quote():
    text='Screenwriters Cindy Davis Hewitt and Donald H. Hewitt wrote English dialogue to match the original Japanese lip movements.'
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=text)]
    assert list(flow.support_sentences(evidence).values()) == [('P1',text)]
    from movie_companion.content_proposals import FactProposal
    item=FactProposal(title='Dialogue fitted to animation',text='The writers fitted English dialogue to the original animated lip movements.',
                      passage_id='P1',evidence_quote=text[text.index('Hewitt wrote'):])
    assert flow.complete_support_quote(evidence,item) is False
    assert flow.complete_support_quote(evidence,item.model_copy(update={'evidence_quote':text})) is True


def test_publication_rechecks_full_source_boundaries_even_if_origin_is_forged(tmp_path,monkeypatch):
    store,saved,r,path,selection,write,snapshots=publication_fixture(tmp_path,monkeypatch)
    snapshot=snapshots['time-arrival'];original=snapshot.source
    text='Screenwriters Cindy Davis Hewitt and Donald H. Hewitt wrote English dialogue to match the original Japanese lip movements.'
    section=SourceSection(0,len(text),'Production','production')
    source=replace(original,text=text,sections=(section,))
    snapshots['time-arrival']=replace(snapshot,source=source)
    r['sources'][0]['text_sha256']=hashlib.sha256(text.encode()).hexdigest()
    c=r['candidates'][0]
    start=text.index('Hewitt wrote');clipped=text[start:]
    c['proposal'].update(title='Dialogue fitted to animation',text='The writers fitted English dialogue to the original animated lip movements.',evidence_quote=clipped)
    c['origin'].update(section_title=section.title,section_category=section.category,start=start,end=len(text))
    c['evidence_sha256']=hashlib.sha256(clipped.encode()).hexdigest()
    write()
    with pytest.raises(ValueError,match='lost support'):
        flow.publish_reviewed(store,report_path=path,selection_path=selection)
    assert store.load(329865)==saved


def test_sentence_helper_changes_invalidate_background_fingerprint(monkeypatch):
    from pathlib import Path
    before=flow.fingerprint();original=Path.read_bytes
    def changed(path):
        return original(path)+(b'\n# changed sentence policy' if path.name=='sentence_spans.py' else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    assert before!=flow.fingerprint()


def test_retrieval_window_cannot_start_quote_after_a_personal_initial(monkeypatch):
    lead='The crew prepared a practical shot for the film. '*10
    name='Screenwriters Cindy Davis Hewitt and Donald H. Hewitt wrote English dialogue to match the original Japanese lip movements.'
    tail='The team carefully recorded every line in the dubbing studio.'
    text=lead+name+' '+(tail+' ')*12
    section=SourceSection(0,len(text),'Production','filming')
    source=SourceDocument('time-arrival',329865,text,'TIME fixture',ARTICLES['time-arrival'].url,'v1','unknown',(section,))
    chunks=source_chunks(source,max_chars=600,overlap_chars=100)
    assert len(lead)<chunks[1].start<text.index('Hewitt wrote')
    passages=[EmbeddedPassage(str(i),329865,c.text,[1.,0.],flow.EMBEDDING,'TIME fixture',
                             section_title='Production',section_category='filming') for i,c in enumerate(chunks)]
    async def ingest(*args,**kwargs):return 'cached'
    async def embed(*args,**kwargs):return [[1.,0.]]
    monkeypatch.setattr(flow,'ingest_source',ingest)
    monkeypatch.setattr(flow,'embed_texts',embed)
    monkeypatch.setattr(flow,'retrieve_passages',lambda *args,**kwargs:[RetrievalHit(passages[1],.9)])
    store=SimpleNamespace(load_snapshot=lambda *args,**kwargs:passages)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            evidence,_=await flow.article_evidence(client,store,SimpleNamespace(source=source))
        assert evidence[0].text.startswith(name)
        assert len(evidence[0].text)<=600
        assert not evidence[0].text.startswith('Hewitt wrote')
        assert source.text[evidence[0].origin.start:evidence[0].origin.end]==evidence[0].text
    asyncio.run(run())


@pytest.mark.parametrize('change',['missing','uncertain','reject','identity'])
def test_publication_rechecks_structured_assessment(tmp_path,monkeypatch,change):
    store,saved,r,path,selection,write,_=publication_fixture(tmp_path,monkeypatch)
    c=r['candidates'][0]
    if change=='missing':c.pop('critic_assessment')
    elif change=='uncertain':c['critic_assessment']['missing_mentions']=['Roger Deakins']
    elif change=='reject':c['critic_assessment']['semantic_decision']='reject'
    else:c['critic_assessment']['item_id']='F2'
    write()
    with pytest.raises(ValueError):flow.publish_reviewed(store,report_path=path,selection_path=selection)
    assert store.load(329865)==saved


def test_publication_recomputes_missing_names_even_with_empty_assessment(tmp_path,monkeypatch):
    store,saved,r,path,selection,write,_=publication_fixture(tmp_path,monkeypatch)
    r['candidates'][0]['proposal']['text']='Roger Deakins built a lighting rig designed for reuse.'
    write()
    with pytest.raises(ValueError,match='lost support'):flow.publish_reviewed(store,report_path=path,selection_path=selection)
    assert store.load(329865)==saved
