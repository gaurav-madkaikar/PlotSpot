"""Movie-scoped corpus retrieval and reviewed additions; scripts are context only."""
import asyncio
from dataclasses import asdict
import json
from uuid import uuid4
from .evidence_store import EvidenceStore,SourceDocument
from .grounding_learning import _parse_answer
from .ingestion_learning import ingest_source
from .movie_qa_learning import answer_movie_question
from .movie_questions import MovieAnswer,QuestionCitation,QuestionError,ScriptContext
from .movie_quiz import QuizItem
from .movie_web_sources import MovieIdentity,normal
from .discussion_support import review_support,MODEL as REVIEW_MODEL
from .research_workflow import prepare_research
from .research_checkpoint import derive,digest,source_map
from .movie_research import ResearchDocument,source_loaders
from .web_corpus_store import registered_source_match

async def bounded_pool(service,passages,by_id,question,movie_id):
    """Rank within each source, preserving adjacent original citation windows."""
    if len(passages)<=400:return passages
    from .embedding_learning import embed_texts
    from .discussion_retrieval import retrieve_discussion_passages
    vector=(await embed_texts(service.ollama,model=service.embedding_model,texts=['search_query: '+question]))[0]
    groups={}
    for p in passages:groups.setdefault(by_id[p.passage_id].source_id,[]).append(p)
    selections=[]
    for group in groups.values():
        hits=retrieve_discussion_passages(question=question,query_vector=vector,passages=group,
            query_model=service.embedding_model,movie_id=movie_id,allow_spoilers=True,k=6)
        positions={p.passage_id:i for i,p in enumerate(group)}
        indices=set()
        for hit in hits:
            i=positions[hit.passage.passage_id]
            indices.update(range(max(0,i-1),min(len(group),i+2)))
        selections.append([group[i] for i in sorted(indices)])
    return [group[i] for i in range(max(map(len,selections),default=0))
            for group in selections if i<len(group)][:400]

def published_background_sources(movie_id):
    """Reuse approved external fact excerpts, not generated fact prose or scripts."""
    from .content_store import ContentStore
    from .source_registry import CALTECH_URL
    from .source_sections import SourceSection
    import hashlib
    saved=ContentStore().load(movie_id)
    if saved is None:return []
    groups={}
    # TIME/BFI are loaded as full reviewed snapshots by source_loaders. Caltech's
    # retained reading record is an abstract; only its approved citation excerpts
    # are available here. Do not represent these as a fresh full-page acquisition.
    for item in saved['facts'].items:
        for citation in item.citations:
            if citation.source_ref==CALTECH_URL:
                groups.setdefault((citation.source_ref,citation.revision,citation.source_label),set()).add(citation.excerpt)
    result=[]
    for (url,revision,label),quotes in groups.items():
        text='\n\n'.join(sorted(quotes))
        key=hashlib.sha256((url+revision+text).encode()).hexdigest()[:20]
        result.append(SourceDocument(f'published-{movie_id}-{key}',movie_id,text,label,url,revision,
            'unknown',(SourceSection(0,len(text),'Approved production excerpts','effects'),)))
    return result

async def source_bundle(service,movie_id,*,purposes=('story','background'),scripts=True):
    identity=await service.identity_loader(movie_id)
    if identity.movie_id!=movie_id:raise ValueError('Movie identity mismatch')
    acquired_task=asyncio.create_task(service.corpus.collect(identity,purposes=purposes,scripts=scripts))
    try:
        import httpx
        try:
            source,primary=await service.load_evidence(movie_id)
            wiki=[source];wiki_error=None
        except (ValueError,OSError,TimeoutError,httpx.HTTPError):
            wiki=[];primary=[];wiki_error='unavailable'
        acquired=await acquired_task
    finally:
        if not acquired_task.done():acquired_task.cancel()
        await asyncio.gather(acquired_task,return_exceptions=True)
    reviewed=[]
    if 'background' in purposes:
        from pathlib import Path
        _,reader=source_loaders(movie_id,sources=Path('.'))
        reviewed=list((await reader()).documents)
    approved=await asyncio.to_thread(published_background_sources,movie_id) if 'background' in purposes else []
    sources=list({s.source_id:s for s in [*wiki,*acquired.sources,*[d.source for d in reviewed],*approved]}.values())
    if not sources:raise QuestionError(503,'Movie evidence sources are temporarily unavailable. Please try again later.')
    if service.store is None:
        from pathlib import Path
        service.store=await asyncio.to_thread(EvidenceStore,Path(__file__).resolve().parents[3]/'data/chroma/app')
    trace={**acquired.trace,'wikipedia':wiki_error or 'available','reviewed_articles':len(reviewed),
           'source_count':len(sources),'degraded':acquired.trace['degraded'] or wiki_error is not None}
    service.source_traces[movie_id]=trace
    return sources,primary,trace

async def answer_multi_source(service,movie_id,request):
    sources,primary,trace=await source_bundle(service,movie_id)
    passages=list(primary);by_id={p.passage_id:sources[0] for p in primary}
    words=set(normal(request.question).split())
    # Script groups are optional draft context; index at most two related groups.
    script=[s for s in sources if registered_source_match(s)=='script']
    script.sort(key=lambda s:-len(words&set(normal(s.text).split())))
    eligible=[s for s in sources if registered_source_match(s)!='script' and (not primary or s is not sources[0])]+script[:2]
    for source in eligible:
        await ingest_source(service.ollama,store=service.store,source=source,model=service.embedding_model,**service.chunk_settings)
        indexed=await asyncio.to_thread(service.store.load_snapshot,source,model=service.embedding_model,**service.chunk_settings)
        passages.extend(indexed);by_id.update({p.passage_id:source for p in indexed})
    total=len(passages)
    passages=await bounded_pool(service,passages,by_id,request.question,movie_id)
    trace={**trace,'retrieval':{'available_passages':total,'candidate_passages':len(passages),'budget':400}}
    by_id={p.passage_id:by_id[p.passage_id] for p in passages}
    result=await answer_movie_question(service.ollama,question=request.question,passages=passages,
        movie_id=movie_id,allow_spoilers=True,embedding_model=service.embedding_model,chat_model=service.chat_model)
    checked=_parse_answer(json.dumps(asdict(result)),set(by_id))
    by_passage={p.passage_id:p for p in passages}
    released=[pid for pid in checked.citation_ids if registered_source_match(by_id[pid])!='script']
    citations=[]
    if checked.status=='answered':
        if not released:return MovieAnswer(status='insufficient_evidence',answer='The available released-film sources do not verify this draft detail.',source_coverage=trace)
        # Review each cited source on its own. Two publishers only count when
        # each independently supports the complete answer.
        from .source_corroboration import review_answer_evidence,corroborate_answer
        from .source_coverage import publisher
        groups={}
        for pid in released:groups.setdefault(by_id[pid].source_id,[]).append(by_passage[pid])
        supported={}
        for source_id,source_passages in groups.items():
            source=by_id[source_passages[0].passage_id]
            exact=await review_answer_evidence(service.ollama,source=source,passages=source_passages,
                question=request.question,answer=checked.answer)
            if exact:supported.setdefault(publisher(source.source_ref),exact)
        if not supported:
            return MovieAnswer(status='insufficient_evidence',answer='The available movie sources do not support a consistent answer.',source_coverage=trace)
        publishers=set(supported)
        citations=[citation for group in supported.values() for citation in group]
        publishers={publisher(c.source_ref) for c in citations}
        if len(publishers)<2:
            extra=await corroborate_answer(service.ollama,documents=[ResearchDocument(s) for s in sources],
                store=service.store,movie_id=movie_id,question=request.question,answer=checked.answer,excluded_publishers=publishers)
            if not extra or len(citations)+len(extra)>3:
                return MovieAnswer(status='insufficient_evidence',answer='Multiple independent movie sources could not verify a consistent answer yet.',
                    source_coverage={**trace,'independent_support':'unavailable'})
            citations.extend(extra);publishers.update(publisher(item.source_ref) for item in extra)
        if len(citations)>3:
            return MovieAnswer(status='insufficient_evidence',answer='The verified answer needs more citation context than this view can safely show.',
                source_coverage={**trace,'independent_support':'citation_budget_exceeded'})
        trace={**trace,'answer_publishers':sorted(publishers),'independent_support':'supported'}
    return MovieAnswer(status=checked.status,answer=checked.answer,citations=citations[:3],source_coverage=trace,
        script_context=ScriptContext(source_ref=script[0].source_ref,version='Unverified screenplay draft; released-film details can differ') if script else None)

async def expand_multi_source_quiz(service,store,*,movie_id,saved):
    sources,_,trace=await source_bundle(service,movie_id,purposes=('story',),scripts=True)
    # Writer answers are drawn from released-film sources, with script context
    # available for phrasing and scene understanding but never sole authority.
    report=await prepare_research(service.ollama,movie_id=movie_id,
        documents=[ResearchDocument(s) for s in sources],store=service.store,saved=saved,refresh=True,
        deadline_seconds=120,targets_override={'facts':0,'questions':min(2,40-len(saved['quiz'].items))})
    _,questions,candidates=derive(report,saved)
    selected=[c for c in candidates if c['kind']=='question' and c['retained']]
    if not selected:raise QuestionError(502,'No new questions passed the multi-source evidence and novelty checks. Your saved quiz is unchanged.')
    mapping=source_map(movie_id,report['sources']);accepted=[]
    for c in selected[:2]:
        proposal=c['proposal'];source=mapping[c['source_id']]
        if registered_source_match(source)=='script':raise ValueError('Draft-only quiz authority')
        quote=proposal['evidence_quote']
        citation=QuestionCitation(passage_id=digest({'revision':source.revision,'origin':c['origin'],'quote':quote})[:32],
            source_label=source.source_label,source_ref=source.source_ref,revision=source.revision,excerpt=quote,
            source_kind='web' if registered_source_match(source)=='web' else 'reviewed',source_verified=registered_source_match(source)=='web')
        accepted.append(QuizItem(id='multi-'+uuid4().hex[:16],origin='generated',kind='plot',question=proposal['question'],
            options=proposal['options'],correct_index=proposal['correct_index'],explanation=quote,citations=[citation]))
    existing=saved['quiz'];items=[q for q in existing.items if q.kind!='interpretation']+accepted+[q for q in existing.items if q.kind=='interpretation']
    updated=existing.model_copy(update={'items':items,'message':f'{len(accepted)} new story questions added.'})
    from .source_coverage import item_publishers
    if len(item_publishers([q for q in items if q.kind!='interpretation']))<2:
        raise QuestionError(502,'Independent sources are still needed for new story questions. Your saved quiz is unchanged.')
    manifest={c.revision:c.source_ref for item in [*items,*saved['facts'].items] for c in item.citations}
    await asyncio.to_thread(store.publish,movie_id,version=saved['version'],source_revision=saved['source_revision'],
        quiz=updated,facts=saved['facts'],source_manifest=manifest,expected_prepared_at=saved['prepared_at'])
    current=await asyncio.to_thread(store.load,movie_id)
    return current['quiz'].model_copy(update={'prepared_at':current['prepared_at'],'content_version':current['version'],
                                            'can_generate_more':len(current['quiz'].items)<38})
