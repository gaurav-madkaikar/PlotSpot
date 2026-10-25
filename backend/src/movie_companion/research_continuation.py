"""Create a bounded continuation from a validated exhausted research report."""
import copy

from .research_checkpoint import derive,digest,source_map,workflow_hash
from .research_jobs import load_bank


def continue_incomplete_report(report,*,max_tasks=50):
    """Keep productive records and reuse frozen evidence for missing targets."""
    if type(max_tasks) is not int or not 1<=max_tasks<=50:
        raise ValueError('Invalid continuation task budget')
    saved=load_bank(report.get('base_collection'))
    facts,questions,candidates=derive(report,saved)
    if report.get('state')!='incomplete' or report.get('phase')!='finished':
        raise ValueError('Only a validated incomplete report can be continued')
    productive={candidate['id'].split('-',1)[0] for candidate in candidates if candidate['ready']}
    plan_by_id={task['id']:task for task in report['plan']}
    records_by_id={record['task_id']:record for record in report['records']}
    kept=[]
    for task in report['plan']:
        if task['id'] in productive:
            kept.append((copy.deepcopy(task),copy.deepcopy(records_by_id[task['id']])))
    if not kept:
        raise ValueError('Incomplete checkpoint has no validated work to preserve')

    coverage=report.get('content_coverage') or {}
    fact_coverage=coverage.get('facts') or {}
    quiz_coverage=coverage.get('quiz') or {}
    purposes=[]
    if fact_coverage.get('items',0)<5 or len(fact_coverage.get('publishers',[]))<2:
        purposes.append('background')
    if quiz_coverage.get('items',0)<10 or len(quiz_coverage.get('publishers',[]))<2:
        purposes.append('story')
    if not purposes:
        raise ValueError('Incomplete checkpoint has no missing content target')

    result=copy.deepcopy(report)
    result['plan']=[];result['records']=[]
    for task,record in kept:
        task['id']=f"t{len(result['plan'])+1}"
        record['task_id']=task['id']
        result['plan'].append(task);result['records'].append(record)
    excluded=set(report.get('excluded_source_ids',[]))
    rejected=set(report.get('operator_rejected_task_ids',[]))
    source_tasks={purpose:[copy.deepcopy(task) for task in report['plan']
                           if (task['purpose']==purpose
                               and task.get('source_id') not in excluded
                               and task['id'] not in rejected)]
                  for purpose in purposes}
    if any(not source_tasks[purpose] for purpose in purposes):
        raise ValueError('No frozen evidence is available for a missing target')
    cursor={purpose:0 for purpose in purposes}
    while len(result['plan'])<max_tasks:
        for purpose in purposes:
            if len(result['plan'])>=max_tasks:break
            choices=source_tasks[purpose]
            task=copy.deepcopy(choices[cursor[purpose]%len(choices)])
            cursor[purpose]+=1
            task['id']=f"t{len(result['plan'])+1}"
            result['plan'].append(task)
    result.update(state='running',phase='reviewing',stop_reason=None,
                  continuation_of=digest(report),continuation_round=int(report.get('continuation_round',0))+1)
    result.pop('content_coverage',None)
    result['facts']=[];result['questions']=[];result['candidates']=[]
    result['facts'],result['questions'],result['candidates']=derive(result,saved)
    return result


def rebase_report(report):
    """Revalidate a checkpoint before adopting the current workflow hash."""
    if report.get('state') not in ('running','needs_review','incomplete'):
        raise ValueError('Checkpoint state cannot be rebased')
    saved=load_bank(report.get('base_collection'))
    facts,questions,candidates=derive(report,saved,check_identity=False)
    if (report.get('facts')!=facts or report.get('questions')!=questions
            or report.get('candidates')!=candidates):
        raise ValueError('Checkpoint output changed under the current validators')
    result=copy.deepcopy(report)
    previous=result.get('workflow_sha256')
    result['workflow_sha256']=workflow_hash()
    result['rebased_from_workflow_sha256']=previous
    derive(result,saved)
    return result


def rebase_running_report(report):
    if report.get('state')!='running':raise ValueError('Only a running checkpoint can be rebased')
    return rebase_report(report)


def frozen_resume_documents(report,movie_id):
    """Rebuild documents from a validated checkpoint instead of live search."""
    if report.get('state')!='running' or report.get('movie_id')!=movie_id:
        raise ValueError('Invalid frozen resume report')
    from .evidence_store import SourceDocument
    from .movie_research import ResearchDocument
    from .research_checkpoint import source_map
    sources=source_map(movie_id,report.get('sources'))
    documents=[ResearchDocument(source) for source in sources.values()]
    trace=copy.deepcopy(report.get('research') or {
        'policy':'frozen-research-resume-v1','model_calls':0,'sources':len(documents)})
    return documents,trace


def _coverage(report,saved):
    from .source_coverage import coverage_record,item_publishers,publisher
    sources=source_map(report['movie_id'],report['sources'])
    saved_facts=[] if saved is None else saved['facts'].items
    saved_quiz=[] if saved is None else [q for q in saved['quiz'].items if q.kind!='interpretation']
    fact_publishers=set(item_publishers(saved_facts));quiz_publishers=set(item_publishers(saved_quiz))
    fact_publishers.update(publisher(sources[c['source_id']].source_ref) for c in report['facts'])
    quiz_publishers.update(publisher(sources[c['source_id']].source_ref) for c in report['questions'])
    fact_publishers.discard(None);quiz_publishers.discard(None)
    new_questions=sum(not candidate.get('corroborates') for candidate in report['questions'])
    return coverage_record(fact_count=len(saved_facts)+len(report['facts']),
        question_count=len(saved_quiz)+new_questions,
        fact_publishers=fact_publishers,quiz_publishers=quiz_publishers)


def refine_review_report(report,*,rejections,excluded_source_ids=(),max_tasks=50):
    """Remove reviewer-rejected tasks and prepare only the resulting gaps."""
    if report.get('state')!='needs_review' or report.get('phase')!='finished':
        raise ValueError('Only a completed review report can be refined')
    if (not isinstance(rejections,dict) or not rejections
            or any(not isinstance(task_id,str) or not isinstance(reason,str) or not reason.strip()
                   for task_id,reason in rejections.items())):
        raise ValueError('Review rejections require task IDs and reasons')
    excluded=set(excluded_source_ids)
    if any(not isinstance(source_id,str) or not source_id for source_id in excluded):
        raise ValueError('Invalid excluded source identity')
    saved=load_bank(report.get('base_collection'))
    derive(report,saved)
    plan_by_id={task['id']:task for task in report['plan']}
    records_by_id={record['task_id']:record for record in report['records']}
    if not set(rejections)<=set(records_by_id):raise ValueError('Rejected task is not completed')
    known_sources={task['source_id'] for task in report['plan']}
    if not excluded<=known_sources:raise ValueError('Excluded source is not in the frozen plan')

    result=copy.deepcopy(report)
    completed=len(report['records'])
    # Keep completed records byte-for-byte so later novelty checkpoints retain
    # their original comparison IDs. Operator-rejected tasks stay in the audit
    # history but derive() prevents them from being selected or published.
    result['plan']=copy.deepcopy(report['plan'][:completed])
    result['records']=copy.deepcopy(report['records'])
    rejected=set(report.get('operator_rejected_task_ids',[]))|set(rejections)
    rejected.update(task['id'] for task in report['plan'][:completed]
                    if task['source_id'] in excluded)
    result['operator_rejected_task_ids']=sorted(rejected,key=lambda task_id:int(task_id[1:]))
    # Unstarted tasks have no checkpoint references and can be filtered and
    # renumbered safely before the append-only replacement budget is added.
    for original in report['plan'][completed:]:
        if original['source_id'] in excluded:continue
        task=copy.deepcopy(original);task['id']=f't{len(result["plan"])+1}'
        result['plan'].append(task)
    result['facts']=[];result['questions']=[];result['candidates']=[]
    result['facts'],result['questions'],result['candidates']=derive(result,saved)
    coverage=_coverage(result,saved)
    original_digest=digest(report)
    previous=list(report.get('review_rejections',[]))
    result['review_rejections']=[*previous,*[{'task_id':task_id,'reason':reason.strip()}
        for task_id,reason in sorted(rejections.items())]]
    result['excluded_source_ids']=sorted(set(report.get('excluded_source_ids',[]))|excluded)
    result['refinement_of']=original_digest
    result['refinement_round']=int(report.get('refinement_round',0))+1
    result['content_coverage']=coverage
    if coverage['complete']:
        result.update(state='needs_review',phase='finished',stop_reason='review_refinement_complete')
        return result

    purposes=[]
    for purpose,key in [('background','facts'),('story','quiz')]:
        branch=coverage[key]
        if branch['items']<(5 if key=='facts' else 10) or len(branch['publishers'])<2:
            purposes.append(purpose)
    choices={purpose:[copy.deepcopy(task) for task in report['plan']
                      if (task['purpose']==purpose and task['source_id'] not in excluded
                          and task['id'] not in rejected)]
             for purpose in purposes}
    if any(not choices[purpose] for purpose in purposes):
        raise ValueError('Review exclusions left no evidence for a missing target')
    cursors={purpose:0 for purpose in purposes}
    while len(result['plan'])<max_tasks:
        for purpose in purposes:
            if len(result['plan'])>=max_tasks:break
            task=copy.deepcopy(choices[purpose][cursors[purpose]%len(choices[purpose])])
            cursors[purpose]+=1;task['id']=f't{len(result["plan"])+1}'
            result['plan'].append(task)
    result.update(state='running',phase='reviewing',stop_reason=None)
    result.pop('content_coverage',None)
    derive(result,saved)
    return result
