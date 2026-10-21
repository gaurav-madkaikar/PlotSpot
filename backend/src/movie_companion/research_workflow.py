"""Bounded multi-source preparation with immutable tasks and durable checkpoints."""
import asyncio,copy,json
from dataclasses import asdict
from time import monotonic

import httpx

from .background_fact_workflow import article_evidence,copied_prose,duplicate
from .background_fact_review import review_proposals as review_facts
from .content_evidence_retrieval import retrieve_draft_evidence
from .content_proposals import ContentProposals,ProposalEvidence,check_proposals
from .content_readiness import fact_readiness,quiz_readiness,POLICY as READINESS
from .evidence_store import SourceDocument
from .local_models import verify_local_model,DIGESTS
from .quiz_novelty import saved_question_pairs
from .research_checkpoint import POLICY,derive,digest,bank_identity,workflow_hash,validate_resume
from .research_generation import generate_batch
from .structured_content_review import review_proposals as review_questions
from .wikipedia_source import MOVIE_ARTICLES
from .discussion_support import review_support,MODEL as SUPPORT_MODEL
from .quiz_answer_support import literal_answer_support,POLICY as LITERAL_SUPPORT
from .saved_quiz_corroboration import corroborate_saved_question


def prioritized_new_background(tasks, limit=15):
    """Balance structured production depth with independent publishers."""
    if type(limit) is not int or not 1 <= limit <= 15:
        raise ValueError('Invalid new-bank background budget')
    wikipedia=[task for task in tasks if task['source_id'].startswith('enwiki-')][:5]
    independent=[task for task in tasks if not task['source_id'].startswith('enwiki-')]
    selected=[]
    for index in range(max(len(wikipedia),len(independent))):
        if index<len(wikipedia):selected.append(wikipedia[index])
        if index<len(independent):selected.append(independent[index])
        if len(selected)>=limit:break
    return selected[:limit]


async def build_plan(client,*,documents,store,targets,strict_diversity=False,new_bank=False,saved=None):
    story,background,targeted=[],[],[]
    from .web_corpus_store import registered_source_match
    for document in documents:
        source=document.source
        kind=registered_source_match(source)
        if kind=='script':continue  # Drafts supplement writing, not correct-answer authority.
        if saved is not None and targets['questions']:
            from .saved_quiz_retrieval import retrieve_saved_quiz_evidence
            from .source_coverage import item_publishers,publisher
            scored=[item for item in saved['quiz'].items if item.kind!='interpretation']
            if publisher(source.source_ref) not in item_publishers(scored):
                try:focused=retrieve_saved_quiz_evidence(source,saved['quiz'])
                except ValueError:focused=[]
                if focused:targeted.append({'purpose':'story','source_id':source.source_id,
                    'evidence':[p.model_dump() for p in focused]})
        if document.article is not None:
            try:evidence,_=await article_evidence(client,store,document.article)
            except (ValueError,OSError,httpx.HTTPError,TimeoutError):continue
            background.append({'purpose':'background','source_id':source.source_id,'evidence':[p.model_dump() for p in evidence]})
            continue
        try:retrieved=await retrieve_draft_evidence(client,source=source,store=store,max_batches=5)
        except (ValueError,OSError,httpx.HTTPError,TimeoutError):continue
        for batch in retrieved.batches:
            for purpose,destination in [('story',story),('background',background)]:
                passages=[p for p in batch if p.purpose==purpose]
                if passages:destination.append({'purpose':purpose,'source_id':source.source_id,'evidence':[p.model_dump() for p in passages]})
    def diverse(tasks, purpose):
        groups={}
        for task in tasks:groups.setdefault(task['source_id'],[]).append(task)
        # One batch from each source before a second batch from any source.
        # Full plot sources are the highest-yield story authority. Production
        # interviews/articles are the highest-yield background authority.
        def rank(source_id):
            if purpose=='story':
                return 0 if source_id.startswith('enwiki-') else 1 if source_id.startswith('tmdb-') else 2
            return 0 if source_id.startswith('web-') else 1 if source_id.startswith('enwiki-') else 2
        groups=dict(sorted(groups.items(),key=lambda pair:rank(pair[0])))
        return [group[i] for i in range(max(map(len,groups.values()),default=0))
                for group in groups.values() if i<len(group)]
    background=diverse(background,'background')
    story=diverse([*targeted,*story],'story')
    # A strict multi-source run gets one additional bounded attempt from each
    # of its first two story publishers. Later attempts see earlier rejected
    # topics, so this does not blindly repeat a duplicate proposal.
    story_sources=list(dict.fromkeys(task['source_id'] for task in story))
    if strict_diversity and targets['questions'] and len(story_sources)>=2:
        expanded=list(story)
        for source_id in story_sources[:2]:
            group=[task for task in story if task['source_id']==source_id]
            if len(group)==1:expanded.append(copy.deepcopy(group[0]))
        story=diverse(expanded,'story')
    if targets['questions']==0:story=[]
    if targets['facts']==0:background=[]
    result=[]
    for i in range(max(len(story),len(background))):
        for tasks in (story,background):
            if i<len(tasks) and len(result)<12:result.append(tasks[i])
    # A new bank needs retry capacity beyond the exact ten-question happy path.
    if new_bank and targets['questions']==10:
        selected=(story[:20],prioritized_new_background(background));result=[]
        for i in range(max(map(len,selected),default=0)):
            for tasks in selected:
                if i<len(tasks) and len(result)<35:result.append(tasks[i])
    for i,task in enumerate(result):task['id']=f't{i+1}'
    return result


def saved_context(saved,report):
    pairs=[] if saved is None else saved_question_pairs(saved['quiz'])
    facts=[] if saved is None else [f.text for f in saved['facts'].items]
    # Invalid drafts remain auditable but must not permanently reserve a topic;
    # a later source may express the same fact with complete evidence and clear
    # wording. Only candidates that passed every current readiness gate become
    # generation memory.
    for candidate in report['candidates']:
        if not candidate['ready'] or candidate.get('corroborates'):continue
        proposal=candidate['proposal']
        if candidate['kind']=='question':
            pairs.append({'question':proposal['question'],'answer':proposal['options'][proposal['correct_index']]})
        else:facts.append(proposal['text'])
    return pairs,facts


async def run_task(client,*,task,source,saved,report,store=None):
    evidence=[ProposalEvidence.model_validate(p) for p in task['evidence']]
    pairs,facts=saved_context(saved,report)
    if (task['purpose']=='story' and saved is not None and report.get('coverage_policy')
            and report['targets']['questions']>len(report['questions'])):
        direct=await corroborate_saved_question(client,source=source,evidence=evidence,quiz=saved['quiz'])
        if direct is not None:
            return {'task_id':task['id'],'proposals':{'facts':[],'questions':[]},
                'review':{'items':[]},'checks':[],'fact_readiness':{},
                'quiz_readiness':{'policy':READINESS,'ready_ids':[],'items':[],'error_type':None},
                'answer_support':{},'saved_answer_support':{},'saved_corroboration':direct}
    contexts=[]
    if task['purpose']=='story':
        from .web_corpus_store import registered_source_match
        for raw in report['sources']:
            supplemental=SourceDocument(**raw)
            if registered_source_match(supplemental)=='script':
                words=set(source.text[:1200].casefold().split())
                blocks=[b for b in supplemental.text.split('\n\n') if 40<=len(b)<=600]
                blocks.sort(key=lambda b:-len(words&set(b.casefold().split())))
                contexts.extend(blocks[:2])
    proposals=await generate_batch(client,source=source,movie_title=MOVIE_ARTICLES[source.movie_id],
        purpose=task['purpose'],evidence=evidence,existing_questions=pairs,existing_facts=facts,
        **({'script_context':contexts[:4]} if contexts else {}))
    reviewer=review_questions if task['purpose']=='story' else review_facts
    review=await reviewer(client,model='qwen3.5:9b',proposals=proposals,evidence=evidence)
    checks=check_proposals(proposals,evidence)
    decisions={d.item_id:d for d in review.items}
    record={'task_id':task['id'],'proposals':proposals.model_dump(),'review':review.model_dump(),
            'checks':checks,'fact_readiness':{},'quiz_readiness':None,'answer_support':{},
            'saved_answer_support':{},'saved_corroboration':None}
    if task['purpose']=='story':
        base=[f'Q{i+1}' for i,c in enumerate(checks) if c['support_checks_passed'] and decisions[f'Q{i+1}'].decision=='accept']
        from types import SimpleNamespace
        quiz=SimpleNamespace(items=[SimpleNamespace(question=p['question'],options=[p['answer']]*4,correct_index=0) for p in pairs])
        record['quiz_readiness']=await quiz_readiness(client,proposals=proposals,quiz=quiz,base_eligible=base)
        for i,proposal in enumerate(proposals.questions):
            alias=f'Q{i+1}'
            answer=proposal.options[proposal.correct_index]
            if literal_answer_support(answer,proposal.evidence_quote):
                record['answer_support'][alias]={'method':LITERAL_SUPPORT}
                continue
            try:
                support=await review_support(client,model=SUPPORT_MODEL,question=proposal.question,
                    answer=answer,quotes=[proposal.evidence_quote])
                record['answer_support'][alias]=asdict(support)
            except (ValueError,httpx.HTTPError,TimeoutError) as error:
                record['answer_support'][alias]={'error_type':'HTTPError' if isinstance(error,httpx.HTTPError) else type(error).__name__}
        if saved is not None:
            scored=[item for item in saved['quiz'].items if item.kind!='interpretation']
            for item in record['quiz_readiness']['items']:
                matches=item.get('matches',[]);alias=item['candidate_id']
                if item.get('novelty')!='duplicate' or len(matches)!=1 or not matches[0].startswith('B'):
                    continue
                index=int(matches[0][1:])-1
                if not 0<=index<len(scored):continue
                proposal=proposals.questions[int(alias[1:])-1]
                target=scored[index]
                try:
                    support=await review_support(client,model=SUPPORT_MODEL,question=target.question,
                        answer=target.options[target.correct_index],quotes=[proposal.evidence_quote])
                    record['saved_answer_support'][alias]=asdict(support)
                except (ValueError,httpx.HTTPError,TimeoutError) as error:
                    record['saved_answer_support'][alias]={'error_type':'HTTPError' if isinstance(error,httpx.HTTPError) else type(error).__name__}
        if registered_source_match(source)=='web':
            from .source_corroboration import corroborate_question
            from .movie_research import ResearchDocument
            record['independent_support']={}
            documents=[ResearchDocument(SourceDocument(**s)) for s in report['sources']]
            for i,proposal in enumerate(proposals.questions):
                proof=await corroborate_question(client,source=source,documents=documents,store=store,
                    question=proposal.question,answer=proposal.options[proposal.correct_index])
                record['independent_support'][f'Q{i+1}']=proof
    else:
        for i,proposal in enumerate(proposals.facts):
            alias=f'F{i+1}'
            base=(checks[i]['support_checks_passed'] and decisions[alias].decision=='accept'
                  and len(proposal.text.split())<=45 and not copied_prose(proposal.text,proposal.evidence_quote)
                  and not duplicate(proposal.text,facts))
            ready=await fact_readiness(client,proposal=proposal,evidence=evidence,source=source,base_eligible=base)
            record['fact_readiness'][alias]=ready
            if ready['ready'] and len(facts)-(len(saved['facts'].items) if saved else 0)<report['targets']['facts']:
                facts.append(proposal.text)
    return record


async def prepare_research(client,*,movie_id,documents,store,saved,checkpoint=None,
                           resume=None,refresh=False,deadline_seconds=600,targets_override=None,require_diverse_sources=False):
    if type(deadline_seconds) not in (int,float) or not .001<=deadline_seconds<=1800:
        raise ValueError('Preparation deadline must be positive and at most 1800 seconds')
    if type(refresh) is not bool or movie_id not in MOVIE_ARTICLES:raise ValueError('Invalid research preparation request')
    began=monotonic()
    targets={'facts':min(5,12-(len(saved['facts'].items) if saved else 0)),
             'questions':min(10,40-(len(saved['quiz'].items) if saved else 0))}
    if require_diverse_sources and saved is not None:
        from .source_coverage import item_publishers
        saved_facts=saved['facts'].items
        saved_quiz=[item for item in saved['quiz'].items if item.kind!='interpretation']
        fact_capacity=max(0,12-len(saved_facts));question_capacity=max(0,40-len(saved['quiz'].items))
        # Existing collections need only their missing quota or one candidate
        # from a new publisher. They should not pay the full new-bank budget.
        targets={
            'facts':min(5,fact_capacity,max(0,5-len(saved_facts),
                1 if len(item_publishers(saved_facts))<2 else 0)),
            'questions':min(10,question_capacity,max(0,10-len(saved_quiz),
                1 if len(item_publishers(saved_quiz))<2 else 0)),
        }
    if targets_override is not None:
        if set(targets_override)!={'facts','questions'} or any(type(n)is not int or not 0<=n<=targets[k] for k,n in targets_override.items()):raise ValueError('Invalid bounded preparation targets')
        targets=targets_override
    sources=sorted([d.source for d in documents],key=lambda s:s.source_id)
    report={'workflow':POLICY,'workflow_sha256':workflow_hash(),'movie_id':movie_id,
        'bank_sha256':bank_identity(saved),'sources':[asdict(s) for s in sources],
        'sources_sha256':digest([asdict(s) for s in sources]),'targets':targets,
        'model_digests':{m:DIGESTS[m] for m in ('nomic-embed-text:v1.5','qwen3.5:9b')},
        'plan':[],'records':[],'facts':[],'questions':[],'candidates':[],
        'publication_approved':False,'saved_collection_changed':False,'reused':False,
        'state':'running','phase':'retrieving','stop_reason':None}
    if require_diverse_sources:
        from .source_coverage import POLICY as COVERAGE
        report['coverage_policy']=COVERAGE
    if resume is not None:
        from .preparation_resume import ResumeMismatch
        from .source_coverage import POLICY as COVERAGE
        expected_coverage=COVERAGE if require_diverse_sources else None
        if resume.get('coverage_policy')!=expected_coverage:
            raise ResumeMismatch('Research coverage policy changed')
        validate_resume(resume,saved,sources)
        report=copy.deepcopy(resume)
        if report['state']!='running':return report
    elif saved is not None and not refresh:
        report.update(reused=True,state='ready',phase='finished',stop_reason='saved_collection_reused')
    def save():
        report['elapsed_seconds']=round(monotonic()-began,3)
        if checkpoint:checkpoint(report)
    save()
    if report['reused']:return report
    try:
        async with asyncio.timeout(deadline_seconds):
            for model in report['model_digests']:await verify_local_model(client,model)
            if not report['plan']:
                report['plan']=await build_plan(client,documents=documents,store=store,targets=targets,
                    strict_diversity=bool(report.get('coverage_policy')),new_bank=saved is None,saved=saved)
                save()
            by_id={s.source_id:s for s in sources}
            for task in report['plan'][len(report['records']):]:
                key='questions' if task['purpose']=='story' else 'facts'
                if len(report[key])>=targets[key]:
                    record={'task_id':task['id'],'proposals':{'facts':[],'questions':[]},
                            'checks':[],'review':{'items':[]},'fact_readiness':{},
                            'quiz_readiness':{'policy':READINESS,'ready_ids':[],'items':[],'error_type':None},
                            'answer_support':{},'saved_answer_support':{},'saved_corroboration':None}
                else:
                    report['phase']='generating';save()
                    try:
                        async with asyncio.timeout(180):
                            record=await run_task(client,task=task,source=by_id[task['source_id']],saved=saved,report=report,store=store)
                    except (ValueError,KeyError,httpx.HTTPError,TimeoutError) as error:
                        record={'task_id':task['id'],'proposals':{'facts':[],'questions':[]},
                            'checks':[],'review':{'items':[]},'fact_readiness':{},
                            'quiz_readiness':{'policy':READINESS,'ready_ids':[],'items':[],'error_type':None},
                            'answer_support':{},'saved_answer_support':{},'saved_corroboration':None,
                            'error_type':'HTTPError' if isinstance(error,httpx.HTTPError) else type(error).__name__}
                report['records'].append(record)
                report['facts'],report['questions'],report['candidates']=derive(report,saved)
                report['phase']='reviewing';save()
                if all(len(report[k])>=n for k,n in targets.items()):
                    report['stop_reason']='targets_reached';break
    except TimeoutError:report['stop_reason']='deadline_exceeded'
    ready=bool(report['facts'] or report['questions'])
    enough=(len(report['facts'])+(len(saved['facts'].items) if saved else 0)>=5
            and len(report['questions'])+(len(saved['quiz'].items) if saved else 0)>=10)
    if report.get('coverage_policy'):
        from .source_coverage import POLICY as COVERAGE,coverage_record,item_publishers,publisher
        if report['coverage_policy']!=COVERAGE:raise ValueError('Unknown research coverage policy')
        mapped={s.source_id:s for s in sources}
        saved_facts=[] if saved is None else saved['facts'].items
        saved_quiz=[] if saved is None else [q for q in saved['quiz'].items if q.kind!='interpretation']
        fact_publishers=set(item_publishers(saved_facts))
        quiz_publishers=set(item_publishers(saved_quiz))
        fact_publishers.update(publisher(mapped[c['source_id']].source_ref) for c in report['facts'])
        quiz_publishers.update(publisher(mapped[c['source_id']].source_ref) for c in report['questions'])
        fact_publishers.discard(None);quiz_publishers.discard(None)
        new_questions=sum(not candidate.get('corroborates') for candidate in report['questions'])
        report['content_coverage']=coverage_record(
            fact_count=len(saved_facts)+len(report['facts']),
            question_count=len(saved_quiz)+new_questions,
            fact_publishers=fact_publishers,quiz_publishers=quiz_publishers)
        enough=report['content_coverage']['complete']
    report.update(state='needs_review' if ready and enough else 'incomplete',phase='finished',
                  stop_reason=report['stop_reason'] or 'evidence_budget_exhausted')
    save();return report
