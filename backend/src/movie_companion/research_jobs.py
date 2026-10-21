"""Durable research worker using the existing queue, leases and model admission."""
import asyncio,json
from time import monotonic
import httpx
from dataclasses import asdict

from .content_store import ContentStore
from .evidence_store import EvidenceStore,SourceDocument
from .movie_facts import MovieFacts
from .movie_quiz import MovieQuiz
from .movie_research import research_movie,source_loaders,ResearchLoad,ResearchDocument
from .preparation_jobs import PreparationJobs,DraftJob,DraftItem,atomic_json
from .proposal_evidence import evidence_pools
from .research_checkpoint import POLICY,derive
from .research_workflow import prepare_research
from .wikipedia_source import fetch_movie_source


def dump_bank(saved):
    return None if saved is None else {k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()}


def load_bank(raw):
    if raw is None:return None
    result={**raw,'facts':MovieFacts.model_validate(raw['facts']),'quiz':MovieQuiz.model_validate(raw['quiz'])}
    ContentStore.validate(result['quiz'],result['facts'])
    ContentStore.validate_manifest(result['quiz'],result['facts'],result['source_revision'],result['source_manifest'])
    return result


def project_research_job(record):
    report=record['report'];saved=load_bank(report.get('base_collection'))
    if report.get('movie_id')!=record['movie_id']:raise ValueError('Research job movie mismatch')
    facts,questions,candidates=derive(report,saved,check_identity=False)
    if report.get('facts')!=facts or report.get('questions')!=questions or report.get('candidates')!=candidates:
        raise ValueError('Retained research checkpoint differs from validated records')
    items=[]
    for c in candidates:
        p=c['proposal']
        items.append(DraftItem(id=c['id'],kind=c['kind'],title=p.get('title',p.get('question','')),
            text=p.get('text',''),options=p.get('options',[]),correct_index=p.get('correct_index'),
            decision=c['decision'],retained=c['retained'],reason=c['reason'][:400],
            evidence_quote=p['evidence_quote'],origin=c['origin']))
    approved=record['state']=='published'
    if approved and (report.get('publication_approved') is not True or not report.get('publication_receipt')):
        raise ValueError('Published state requires an operator publication receipt')
    return DraftJob(**{k:v for k,v in record.items() if k!='report'},
        facts_retained=len(facts),questions_retained=len(questions),batches_completed=len(report['records']),
        items=items,publication_approved=approved)


class ResearchPreparationJobs(PreparationJobs):
    def __init__(self,*args,bank_store=None,article_cache=None,corpus=None,identity_loader=None,
                 require_diverse_sources=False,deadline_seconds=600,**kwargs):
        if type(deadline_seconds) not in (int,float) or not 1<=deadline_seconds<=1800:
            raise ValueError('Invalid research job deadline')
        self.corpus=corpus;self.identity_loader=identity_loader
        self.require_diverse_sources=require_diverse_sources
        self.deadline_seconds=deadline_seconds
        self.bank_store=bank_store or ContentStore()
        self.article_cache=article_cache
        super().__init__(*args,**kwargs)

    async def _research_sources(self,movie_id):
        async def read_wiki():
            path=self.sources/f'{movie_id}.json'
            if path.exists():
                if path.stat().st_size>1_000_000:raise ValueError('Source snapshot exceeds budget')
                source=SourceDocument(**json.loads(await asyncio.to_thread(path.read_text)))
            else:
                source=await fetch_movie_source(self.wiki,movie_id=movie_id)
                evidence_pools(source)
                await asyncio.to_thread(atomic_json,path,asdict(source))
            evidence_pools(source)
            if source.movie_id!=movie_id:raise ValueError('Movie source mismatch')
            return source
        if self.corpus is not None:
            identity=await self.identity_loader(movie_id)
            wiki,acquired=await asyncio.gather(read_wiki(),self.corpus.collect(identity),return_exceptions=True)
            documents={};errors=[]
            if isinstance(wiki,Exception):errors.append({'source':'wikipedia','error_type':type(wiki).__name__})
            else:documents[wiki.source_id]=ResearchDocument(wiki)
            if isinstance(acquired,Exception):errors.append({'source':'web','error_type':type(acquired).__name__})
            else:
                from .web_corpus_store import registered_source_match
                # Draft screenplays are optional writing context. Keep at most
                # two bounded parts in durable checkpoints; they never count as
                # released-film authority or publication diversity.
                scripts=[s for s in acquired.sources if registered_source_match(s)=='script'][:2]
                released=[s for s in acquired.sources if registered_source_match(s)!='script']
                documents.update({s.source_id:ResearchDocument(s) for s in [*released,*scripts]})
            _,reader=source_loaders(movie_id,sources=self.sources,**({'article_cache':self.article_cache} if self.article_cache else {}))
            reviewed=await reader()
            documents.update({d.source.source_id:d for d in reviewed.documents})
            if not documents:raise ValueError('No usable movie source evidence available')
            return list(documents.values()),{'policy':'multi-source-research-v1','model_calls':0,
                'corpus':None if isinstance(acquired,Exception) else acquired.trace,'errors':errors,'sources':len(documents)}
        shared=asyncio.create_task(read_wiki())
        async def story():return ResearchLoad((ResearchDocument(await asyncio.shield(shared)),))
        async def background():
            options={'article_cache':self.article_cache} if self.article_cache else {}
            _,reader=source_loaders(movie_id,sources=self.sources,**options)
            articles=await reader()
            if articles.documents:return articles
            source=await asyncio.shield(shared)
            if evidence_pools(source)['background']:
                return ResearchLoad((ResearchDocument(source),),articles.errors)
            return articles
        try:
            research=await research_movie(movie_id=movie_id,story_loader=story,background_loader=background)
            documents={d.source.source_id:d for b in research.branches for d in b.documents}
            if not documents:raise ValueError('No registered source evidence available')
            return list(documents.values()),research.trace()
        finally:
            if not shared.done():shared.cancel()
            try:await shared
            except (asyncio.CancelledError,ValueError,OSError,httpx.HTTPError):pass

    async def _prepare(self,movie_id,checkpoint):
        async with asyncio.timeout(self.deadline_seconds):
            return await self._prepare_bounded(movie_id,checkpoint,monotonic()+self.deadline_seconds)

    async def _prepare_bounded(self,movie_id,checkpoint,deadline):
        resume=self.active.get('report') if self.active else None
        if resume and resume.get('workflow')!=POLICY:
            return await super()._prepare(movie_id,checkpoint)  # preserved legacy queue jobs
        saved=await asyncio.to_thread(self.bank_store.load,movie_id)
        refresh=bool(self.active.get('refresh',False)) if self.active else False
        if saved is not None and not refresh and resume is None:
            documents=[];trace={'saved_collection_reused':True};store=None
        else:
            documents,trace=await self._research_sources(movie_id)
            store=await asyncio.to_thread(EvidenceStore,self.evidence_path)
        def persist(report):
            report['base_collection']=dump_bank(saved)
            report['research']=trace
            checkpoint(report)
        return await prepare_research(self.ollama,movie_id=movie_id,documents=documents,store=store,
            saved=saved,checkpoint=persist,resume=resume,refresh=refresh,
            deadline_seconds=max(.001,deadline-monotonic()),
            require_diverse_sources=self.require_diverse_sources)
