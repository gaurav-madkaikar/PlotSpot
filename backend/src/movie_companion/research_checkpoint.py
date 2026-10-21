"""Revalidate frozen research tasks and derive retained content without inference."""
from dataclasses import asdict
import hashlib,json
from pathlib import Path

from .background_fact_workflow import complete_source_quote,copied_prose,duplicate
from .background_registry import ARTICLES
from .content_proposals import ContentProposals,EvidenceOrigin,validate_evidence,check_proposals
from .structured_content_review import StructuredReview,decision_for as question_decision
from .background_fact_review import FactReview,decision_for as fact_decision,missing_mentions
from .content_readiness import fact_precheck,purpose_clauses,POLICY as READINESS
from .evidence_store import SourceDocument
from .local_models import DIGESTS
from .preparation_resume import ResumeMismatch
from .proposal_evidence import evidence_pools,verify_origins
from .quiz_novelty import saved_question_pairs,normalized,deterministic_topic
from .quiz_question_shape import recognized_wording

POLICY='reviewed-research-workflow-v1'
FILES=('research_checkpoint.py','research_workflow.py','research_generation.py',
       'quiz_narrative_quality.py','quiz_novelty.py','quiz_question_shape.py','content_readiness.py','discussion_support.py',
       'content_evidence_retrieval.py','background_fact_workflow.py','background_fact_review.py',
       'structured_content_review.py','content_proposal_review.py','content_proposals.py','proposal_evidence.py',
       'source_sections.py','sentence_spans.py','retrieval_learning.py','ingestion_learning.py',
       'embedding_learning.py','ollama_learning.py','evidence_store.py','local_models.py',
       'background_articles.py','background_registry.py','wikipedia_source.py',
       'wikipedia_references.py',
       'research_jobs.py','research_publication.py','movie_research.py',
       'web_search.py','web_search_worker.py','public_web.py','movie_web_sources.py',
       'web_corpus_store.py','movie_source_corpus.py','multi_source_pipeline.py','source_corroboration.py','source_coverage.py',
       'quiz_answer_support.py','saved_quiz_corroboration.py','saved_quiz_retrieval.py')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def workflow_hash():
    root=Path(__file__).parent
    return digest({name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})

def bank_identity(saved):
    return digest(None if saved is None else {k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()})


def final_slot_allows_publisher(destination, *, source_ref, target, enforce):
    """Reserve the last quota slot when every retained item has one publisher."""
    if not enforce or target < 2 or len(destination) != target-1:
        return True
    from .source_coverage import publisher
    families={publisher(item['origin']['source_ref']) for item in destination}
    families.discard(None)
    candidate=publisher(source_ref)
    return len(families)!=1 or candidate not in families

def source_map(movie_id,raw):
    if not isinstance(raw,list) or not 1<=len(raw)<=32:raise ValueError('Invalid research source budget')
    result={}
    for record in raw:
        source=SourceDocument(**record)
        if source.movie_id!=movie_id or source.source_id in result:raise ValueError('Invalid research source identity')
        from .web_corpus_store import registered_source_match
        if registered_source_match(source):evidence_pools(source)
        elif source.revision.startswith('enwiki-'):evidence_pools(source)
        else:
            article=ARTICLES.get(source.source_id)
            if article is None or article.movie_id!=movie_id or source.source_ref!=article.url:
                raise ValueError('Unregistered research article')
        result[source.source_id]=source
    return result

def plan_tasks(movie_id,sources,raw):
    if not isinstance(raw,list) or len(raw)>50:raise ValueError('Invalid task plan')
    result=[]
    for index,task in enumerate(raw):
        if (set(task)!={'id','purpose','source_id','evidence'} or task['id']!=f't{index+1}'
                or task['purpose'] not in ('story','background') or task['source_id'] not in sources):
            raise ValueError('Invalid frozen task')
        from .web_corpus_store import registered_source_match
        if registered_source_match(sources[task['source_id']])=='script':
            raise ValueError('A screenplay draft cannot be answer authority')
        evidence=validate_evidence(task['evidence'])
        if len(evidence)>2 or any(p.purpose!=task['purpose'] for p in evidence):raise ValueError('Invalid task scope')
        verify_origins(sources[task['source_id']],evidence)
        result.append((task,evidence))
    return result

def support_verdict(raw,quote):
    if (not isinstance(raw,dict) or set(raw)!={'verdict','reason','evidence_answer','evidence_quotes'}
            or raw['verdict'] not in ('supported','unsupported','uncertain')
            or not isinstance(raw['reason'],str) or not 1<=len(raw['reason'].strip())<=250
            or not isinstance(raw['evidence_answer'],str) or not 1<=len(raw['evidence_answer'].strip())<=600
            or not isinstance(raw['evidence_quotes'],(list,tuple)) or len(raw['evidence_quotes'])>1
            or any(q!=quote for q in raw['evidence_quotes'])):raise ValueError('Invalid citation review proof')
    if raw['verdict']=='supported' and (not raw['evidence_quotes'] or raw['evidence_answer']=='Insufficient evidence.'):
        raise ValueError('Invalid positive citation review')
    return raw['verdict']

def fact_ready(raw,*,proposal,evidence,source,base):
    if not isinstance(raw,dict) or raw.get('policy')!=READINESS or type(raw.get('ready')) is not bool:
        raise ValueError('Invalid fact readiness checkpoint')
    reasons,missing=fact_precheck(proposal=proposal,evidence=evidence,source=source,base_eligible=base)
    if raw.get('error_type'):
        if raw['error_type'] not in ('ValueError','HTTPError','TimeoutError'):raise ValueError('Invalid readiness error')
        expected=False
    elif reasons:
        if raw.get('reasons')!=reasons or raw.get('support_review') is not None:
            raise ValueError('Fact deterministic checks changed')
        if missing and raw.get('missing_mentions')!=missing:raise ValueError('Citation names changed')
        expected=False
    else:
        verdict=support_verdict(raw.get('support_review'),proposal.evidence_quote)
        views=raw.get('purpose_reviews',[])
        clauses=purpose_clauses(proposal.text) if verdict=='supported' else []
        if not isinstance(views,list) or len(views)!=len(clauses):raise ValueError('Missing purpose checks')
        purpose_supported=True
        for view,(action,purpose) in zip(views,clauses):
            if set(view)!={'action','purpose','review'} or view['action']!=action or view['purpose']!=purpose:
                raise ValueError('Purpose context changed')
            purpose_supported &= support_verdict(view['review'],proposal.evidence_quote)=='supported'
        expected=verdict=='supported' and purpose_supported
    if raw['ready']!=expected:raise ValueError('Fact readiness flag was changed')
    return expected

def quiz_ready(raw,proposals,base,pairs):
    if not isinstance(raw,dict) or raw.get('policy')!=READINESS:raise ValueError('Invalid quiz readiness')
    expected=[];ids={f'Q{i+1}' for i in range(len(proposals.questions))}
    if raw.get('error_type'):
        if raw['error_type'] not in ('ValueError','HTTPError','TimeoutError') or raw.get('items'):
            raise ValueError('Invalid quiz failure checkpoint')
    elif base:
        items=raw.get('items')
        if not isinstance(items,list) or len(items)!=len(ids):raise ValueError('Incomplete topic reviews')
        seen=set()
        for item in items:
            cid=item.get('candidate_id')
            if (cid not in ids or cid in seen or item.get('novelty') not in ('new','duplicate','uncertain')
                    or item.get('clarity') not in ('clear','needs_edit','not_reviewed')):
                raise ValueError('Invalid topic checkpoint')
            seen.add(cid);index=int(cid[1:])-1
            matches=item.get('matches');allowed={f'B{i+1}' for i in range(len(pairs))}|{f'Q{i+1}' for i in range(index)}
            if (not isinstance(matches,(list,tuple)) or any(not isinstance(m,str) for m in matches)
                    or not set(matches)<=allowed or len(set(matches))!=len(matches)
                    or item['novelty']=='new' and matches or item['novelty']=='duplicate' and not matches):
                raise ValueError('Topic match IDs changed')
            proposal=proposals.questions[index]
            candidate={'id':cid,'question':proposal.question,'answer':proposal.options[proposal.correct_index]}
            previous=[{'id':f'B{i+1}',**pair} for i,pair in enumerate(pairs)]
            previous += [{'id':f'Q{i+1}','question':p.question,'answer':p.options[p.correct_index]} for i,p in enumerate(proposals.questions[:index])]
            fixed=deterministic_topic(candidate,previous)
            if fixed and (item['novelty']!=fixed.novelty or tuple(matches)!=fixed.matches
                          or fixed.clarity!='not_reviewed' and item['clarity']!=fixed.clarity):
                raise ValueError('Deterministic topic review changed')
            if item['novelty']=='new' and recognized_wording(candidate['question'],candidate['answer']) and item['clarity']!='clear':
                raise ValueError('Deterministic wording review changed')
            ready=cid in base and item['novelty']=='new' and item.get('clarity')=='clear'
            if type(item.get('ready')) is not bool or item['ready']!=ready:raise ValueError('Quiz ready flag changed')
            if ready:expected.append(cid)
    if raw.get('ready_ids')!=expected:raise ValueError('Quiz selections changed')
    return set(expected)

def independent_support(proof,sources,original):
    """A supported web question needs retained independent Wikipedia evidence."""
    if not isinstance(proof,dict) or proof.get('status')!='supported':return False
    reference=sources.get(proof.get('source_id'))
    quotes=proof.get('evidence');review=proof.get('review')
    from .source_coverage import publisher
    if (reference is None or reference.source_id==original.source_id
            or publisher(reference.source_ref) in (None,publisher(original.source_ref))
            or proof.get('revision')!=reference.revision
            or not isinstance(quotes,list) or not 1<=len(quotes)<=5
            or any(not isinstance(q,str) or not 20<=len(q)<=600 or q not in reference.text for q in quotes)
            or not isinstance(review,dict) or set(review)!={'verdict','reason','evidence_answer','evidence_quotes'}
            or review['verdict']!='supported' or not isinstance(review['reason'],str) or not 1<=len(review['reason'])<=250
            or not isinstance(review['evidence_answer'],str) or not 1<=len(review['evidence_answer'])<=600
            or review['evidence_answer']=='Insufficient evidence.'
            or not isinstance(review['evidence_quotes'],(list,tuple)) or not 1<=len(review['evidence_quotes'])<=3
            or any(q not in quotes for q in review['evidence_quotes'])):
        raise ValueError('Independent source support proof changed')
    return True

def derive(report,saved,*,check_identity=True):
    """Retain only validated, reviewed, bounded candidates. No model calls."""
    if (not isinstance(report,dict) or report.get('workflow')!=POLICY
            or report.get('bank_sha256')!=bank_identity(saved)
            or report.get('model_digests')!={m:DIGESTS[m] for m in ('nomic-embed-text:v1.5','qwen3.5:9b')}):
        raise ResumeMismatch('Saved bank or model policy changed')
    if check_identity and report.get('workflow_sha256')!=workflow_hash():raise ResumeMismatch('Workflow implementation changed')
    if report.get('reused'):
        if saved is None or report.get('records') or report.get('plan'):raise ValueError('Invalid saved-bank reuse')
        return [],[],[]
    sources=source_map(report['movie_id'],report['sources'])
    if report.get('sources_sha256')!=digest(report['sources']):raise ValueError('Source plan changed')
    tasks=plan_tasks(report['movie_id'],sources,report['plan'])
    targets=report['targets']
    if (set(targets)!={'facts','questions'} or any(type(n) is not int for n in targets.values())
            or not 0<=targets['facts']<=5 or not 0<=targets['questions']<=10):raise ValueError('Invalid retained targets')
    records=report['records']
    if not isinstance(records,list) or len(records)>len(tasks):raise ValueError('Invalid completed task count')
    operator_rejections=report.get('operator_rejected_task_ids',[])
    completed_ids={record.get('task_id') for record in records}
    if (not isinstance(operator_rejections,list)
            or len(set(operator_rejections))!=len(operator_rejections)
            or any(not isinstance(task_id,str) or task_id not in completed_ids
                   for task_id in operator_rejections)):
        raise ValueError('Invalid operator review rejections')
    operator_rejections=set(operator_rejections)
    facts,questions,candidates=[],[],[]
    previous_facts=[] if saved is None else [f.text for f in saved['facts'].items]
    pairs=[] if saved is None else saved_question_pairs(saved['quiz'])
    for index,record in enumerate(records):
        task,evidence=tasks[index];source=sources[task['source_id']]
        candidate_offset=len(candidates)
        if record.get('task_id')!=task['id']:raise ValueError('Completed task order changed')
        proposals=ContentProposals.model_validate(record['proposals'])
        if (task['purpose']=='story' and proposals.facts or task['purpose']=='background' and proposals.questions
                or len(proposals.facts)>2 or len(proposals.questions)>3):raise ValueError('Draft role budget violated')
        checks=check_proposals(proposals,evidence)
        if record['checks']!=checks:raise ValueError('Support checks changed')
        critic = StructuredReview if task['purpose']=='story' else FactReview
        decisions=critic.model_validate(record['review']).items
        reviews={d.item_id:d for d in decisions}
        expected={f'{prefix}{i+1}' for prefix,items in [('F',proposals.facts),('Q',proposals.questions)] for i in range(len(items))}
        if set(reviews)!=expected or len(reviews)!=len(decisions):raise ValueError('Missing critic decisions')
        for check in checks:
            kind=check['kind'];i=check['index'];alias=('Q' if kind=='question' else 'F')+str(i+1)
            decision=reviews[alias];assessment=decision.assessment
            if not check['support_checks_passed']:
                if decision.decision!='reject' or assessment is not None:
                    raise ValueError('Deterministic critic rejection changed')
                continue
            if assessment is None or assessment.item_id!=alias:raise ValueError('Missing critic assessment')
            if kind=='question':
                expected_decision=question_decision(assessment,kind=kind,correct_index=proposals.questions[i].correct_index)
            else:
                proposal=proposals.facts[i];passage=next(p for p in evidence if p.passage_id==proposal.passage_id)
                if assessment.missing_mentions!=missing_mentions(proposal.text,passage):
                    raise ValueError('Source-name assessment changed')
                expected_decision=fact_decision(assessment)
            if decision.decision!=expected_decision:raise ValueError('Critic assessment and decision disagree')
        base_quiz=[f'Q{i+1}' for i,c in enumerate(checks) if task['purpose']=='story' and c['support_checks_passed'] and reviews[f'Q{i+1}'].decision=='accept']
        ready_ids=quiz_ready(record['quiz_readiness'],proposals,base_quiz,pairs) if task['purpose']=='story' else set()
        answer_support=record.get('answer_support')
        expected_support={f'Q{i+1}' for i in range(len(proposals.questions))}
        if not isinstance(answer_support,dict) or set(answer_support)!=expected_support:
            raise ValueError('Missing complete-answer support checks')
        saved_answer_support=record.get('saved_answer_support')
        expected_saved_support=set()
        if task['purpose']=='story' and saved is not None:
            saved_scored=[item for item in saved['quiz'].items if item.kind!='interpretation']
            for item in record['quiz_readiness']['items']:
                matches=item.get('matches',[])
                if (item.get('novelty')=='duplicate' and len(matches)==1 and matches[0].startswith('B')
                        and int(matches[0][1:])-1<len(saved_scored)):
                    expected_saved_support.add(item['candidate_id'])
        if not isinstance(saved_answer_support,dict) or set(saved_answer_support)!=expected_saved_support:
            raise ValueError('Invalid saved-answer support checks')
        if 'saved_corroboration' not in record:raise ValueError('Missing saved corroboration checkpoint')
        direct=record['saved_corroboration']
        if direct is not None:
            from .saved_quiz_corroboration import POLICY as SAVED_CORROBORATION
            from .source_coverage import item_publishers,publisher
            if (task['purpose']!='story' or saved is None or proposals.questions or proposals.facts
                    or set(direct)!={'policy','target_id','question','options','correct_index','passage_id',
                                     'evidence_quote','origin','review'}
                    or direct['policy']!=SAVED_CORROBORATION):
                raise ValueError('Invalid saved corroboration checkpoint')
            scored=[item for item in saved['quiz'].items if item.kind!='interpretation']
            target=next((item for item in scored if item.id==direct['target_id']),None)
            if (target is None or direct['question']!=target.question or direct['options']!=target.options
                    or direct['correct_index']!=target.correct_index
                    or publisher(source.source_ref) in item_publishers(scored)
                    or support_verdict(direct['review'],direct['evidence_quote'])!='supported'):
                raise ValueError('Saved question support changed')
            parent=next((item for item in evidence if item.passage_id==direct['passage_id']),None)
            origin=EvidenceOrigin.model_validate(direct['origin'])
            if (parent is None or parent.origin is None or origin.source_id!=source.source_id
                    or origin.revision!=source.revision or origin.source_ref!=source.source_ref
                    or origin.start<parent.origin.start or origin.end>parent.origin.end
                    or not complete_source_quote(source,origin,direct['evidence_quote'])):
                raise ValueError('Saved corroboration citation changed')
            retained=task['id'] not in operator_rejections and len(questions)<targets['questions']
            candidate={'id':task['id']+'-C1','kind':'question','proposal':{
                    'question':target.question,'options':target.options,'correct_index':target.correct_index,
                    'passage_id':direct['passage_id'],'evidence_quote':direct['evidence_quote']},
                'origin':origin.model_dump(),'decision':'accept',
                'reason':'The exact saved answer is supported by this independent source.',
                'ready':True,'retained':retained,'source_id':source.source_id,'corroborates':target.id}
            candidates.append(candidate)
            if retained:questions.append(candidate)
        items=proposals.questions if task['purpose']=='story' else proposals.facts
        for i,proposal in enumerate(items):
            prefix='Q' if task['purpose']=='story' else 'F';alias=f'{prefix}{i+1}'
            passage=next((p for p in evidence if p.passage_id==proposal.passage_id),None)
            if passage is None:raise ValueError('Unknown proposal passage')
            base=checks[i]['support_checks_passed'] and reviews[alias].decision=='accept'
            corroborates=None
            if prefix=='F':
                base=base and len(proposal.text.split())<=45 and not copied_prose(proposal.text,proposal.evidence_quote) and not duplicate(proposal.text,previous_facts)
                ready=fact_ready(record['fact_readiness'][alias],proposal=proposal,evidence=evidence,source=source,base=base)
                destination=facts;key='facts'
            else:
                proof=answer_support[alias]
                if isinstance(proof,dict) and set(proof)=={'method'}:
                    from .quiz_answer_support import literal_answer_support,POLICY as LITERAL_SUPPORT
                    if proof['method']!=LITERAL_SUPPORT:
                        raise ValueError('Unknown literal answer support policy')
                    answer_ready=literal_answer_support(proposal.options[proposal.correct_index],proposal.evidence_quote)
                    if not answer_ready:raise ValueError('Literal answer support changed')
                elif isinstance(proof,dict) and set(proof)=={'error_type'}:
                    if proof['error_type'] not in ('ValueError','HTTPError','TimeoutError'):
                        raise ValueError('Invalid answer support error')
                    answer_ready=False
                else:answer_ready=support_verdict(proof,proposal.evidence_quote)=='supported'
                base=base and answer_ready
                ready=alias in ready_ids and answer_ready;destination=questions;key='questions'
                from .web_corpus_store import registered_source_match
                if registered_source_match(source)=='web':
                    ready=ready and independent_support(record.get('independent_support',{}).get(alias),sources,source)
                if (not ready and base and report.get('coverage_policy') and saved is not None):
                    novelty=next((item for item in record['quiz_readiness']['items'] if item['candidate_id']==alias),None)
                    matches=[] if novelty is None else novelty['matches']
                    if novelty and novelty['novelty']=='duplicate' and len(matches)==1 and matches[0].startswith('B'):
                        index=int(matches[0][1:])-1
                        scored=[item for item in saved['quiz'].items if item.kind!='interpretation']
                        if index<len(scored):
                            target=scored[index]
                            from .source_coverage import item_publishers,publisher
                            existing=scored
                            source_publisher=publisher(source.source_ref)
                            target_proof=saved_answer_support.get(alias)
                            target_ready=(isinstance(target_proof,dict) and set(target_proof)!={'error_type'}
                                          and support_verdict(target_proof,proposal.evidence_quote)=='supported')
                            if (target_ready and len(target.citations)<3 and source_publisher
                                    and source_publisher not in item_publishers(existing)):
                                corroborates=target.id;ready=True
            if report.get('coverage_policy') and saved is not None and corroborates is None:
                from .source_coverage import item_publishers,publisher
                existing=(saved['facts'].items if prefix=='F' else
                          [item for item in saved['quiz'].items if item.kind!='interpretation'])
                # Strict enrichment spends its small target only on a publisher
                # that changes actual saved-bank coverage.
                if publisher(source.source_ref) in item_publishers(existing):ready=False
            # Code-owned whole-sentence support and exact-string uniqueness remain
            # necessary even when a semantic judgement says ready.
            if not complete_source_quote(source,passage.origin,proposal.evidence_quote):raise ValueError('Incomplete selected citation')
            if (prefix=='Q' and corroborates is None
                    and any(normalized(proposal.question)==normalized(p['question']) for p in pairs)):ready=False
            retained=(ready and task['id'] not in operator_rejections and len(destination)<targets[key]
                and final_slot_allows_publisher(destination,source_ref=source.source_ref,
                    target=targets[key],enforce=bool(report.get('coverage_policy') and saved is None)))
            candidate={'id':task['id']+'-'+alias,'kind':'question' if prefix=='Q' else 'fact',
                'proposal':proposal.model_dump(),'origin':passage.origin.model_dump(),
                'decision':reviews[alias].decision,'reason':reviews[alias].reason,
                'ready':ready,'retained':retained,'source_id':source.source_id}
            if prefix=='Q' and corroborates is not None:candidate['corroborates']=corroborates
            if task['id'] in operator_rejections:candidate['operator_rejected']=True
            candidates.append(candidate)
            if retained:
                destination.append(candidate)
            if prefix=='F' and ready:previous_facts.append(proposal.text)
        if task['purpose']=='story':
            pairs.extend({'question':candidate['proposal']['question'],
                          'answer':candidate['proposal']['options'][candidate['proposal']['correct_index']]}
                         for candidate in candidates[candidate_offset:]
                         if candidate['kind']=='question' and candidate['ready'] and not candidate.get('corroborates'))
    return facts,questions,candidates

def validate_resume(report,saved,sources):
    try:
        facts,questions,candidates=derive(report,saved)
        if not report.get('reused') and digest([asdict(s) for s in sources])!=report['sources_sha256']:
            raise ValueError('Registered source revision changed')
        if report.get('facts')!=facts or report.get('questions')!=questions or report.get('candidates')!=candidates:
            raise ValueError('Checkpoint retained items changed')
        return facts,questions,candidates
    except (ValueError,KeyError,TypeError) as error:
        raise ResumeMismatch('Research checkpoint differs from its source, reviews or policy') from error
