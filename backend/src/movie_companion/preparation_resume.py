"""Validate frozen evidence and replay completed draft batches without inference."""
import copy
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path

from .content_proposals import ContentProposals, validate_evidence, check_proposals
from .content_proposal_review import DraftDecision
from .local_models import DIGESTS
from .proposal_evidence import verify_origins


class ResumeMismatch(ValueError):
    """A checkpoint cannot be continued under the current source or policy."""


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def identity(source,model,review_model,reviewer,max_batches):
    directory=Path(__file__).parent
    files=['content_preparation.py','preparation_resume.py','content_proposal_learning.py',
           'content_proposal_review.py','content_proposals.py','proposal_evidence.py',
           'content_evidence_retrieval.py','source_sections.py','local_models.py']
    implementation={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in files}
    reviewer_path=inspect.getsourcefile(reviewer)
    if reviewer_path:
        implementation['selected_reviewer']=hashlib.sha256(Path(reviewer_path).read_bytes()).hexdigest()
    return {'resume_version':1,'workflow_sha256':digest(implementation),
            'source_sha256':digest(asdict(source)),'max_batches':max_batches,
            'reviewer_name':reviewer.__qualname__,
            'model_digests':{model:DIGESTS.get(model),review_model:DIGESTS.get(review_model)}}


def validate_plan(source,raw,max_batches):
    if not isinstance(raw,list) or not 1 <= len(raw) <= max_batches:
        raise ValueError('Invalid frozen evidence plan')
    plan=[]
    for batch in raw:
        if not isinstance(batch,list) or not 1 <= len(batch) <= 4:
            raise ValueError('Invalid evidence batch budget')
        evidence=validate_evidence(batch)
        verify_origins(source,evidence)
        plan.append(evidence)
    return plan


def apply_record(report,record,duplicate):
    """Recompute retained items; never trust a checkpoint's retention booleans."""
    proposals=ContentProposals.model_validate(record['proposals'])
    evidence=validate_evidence(record['evidence'])
    checks=check_proposals(proposals,evidence)
    if record['checks'] != checks:
        raise ValueError('Proposal support checks changed')
    raw_reviews=record['review']['items']
    decisions=[DraftDecision.model_validate({key:d[key] for key in ('item_id','decision','reason')}) for d in raw_reviews]
    by_id={d.item_id:d for d in decisions}
    expected={f'{prefix}{i+1}' for prefix,items in [('F',proposals.facts),('Q',proposals.questions)] for i,_ in enumerate(items)}
    if len(by_id)!=len(decisions) or set(by_id)!=expected:
        raise ValueError('Incomplete or duplicate checkpoint reviews')
    selection=[]
    offset=0
    for kind,items,key,prefix in [('fact',proposals.facts,'facts','F'),('question',proposals.questions,'questions','Q')]:
        for index,item in enumerate(items):
            decision=by_id[f'{prefix}{index+1}']
            reason=decision.decision if decision.decision!='accept' else duplicate(item.model_dump(),report[key],kind)
            if reason is None and not checks[offset+index]['support_checks_passed']:
                reason='support_checks_failed'
            if reason is None and len(report[key])>=report['targets'][key]:
                reason='target_already_reached'
            selection.append({'item_id':decision.item_id,'retained':reason is None,'reason':reason or 'critic_accepted_draft'})
            if reason is None:
                passage=next(p for p in evidence if p.passage_id==item.passage_id)
                report[key].append({**item.model_dump(),'origin':passage.origin.model_dump(),
                                    'batch':record['batch'],'critic_reason':decision.reason})
        offset+=len(items)
    return selection


def restore(source,expected,resume,duplicate):
    """Return validated report/plan; mismatches fail before any model request."""
    try:
        if not isinstance(resume,dict) or len(json.dumps(resume))>900_000:
            raise ValueError('Invalid checkpoint budget')
        keys=['movie_id','generator_model','critic_model','generator_policy',
              'generator_implementation_sha256','verifier_module','source_manifest',
              'targets','publication_approved','saved_collection_changed','evidence_mode',
              'resume_version','workflow_sha256','source_sha256','max_batches','model_digests','reviewer_name']
        if any(resume.get(k)!=expected[k] for k in keys):
            raise ValueError('Checkpoint source or policy changed')
        if resume.get('publication_approved') is not False or resume.get('saved_collection_changed') is not False:
            raise ValueError('Checkpoint has publication authority')
        if resume.get('state') not in {'running','needs_review','incomplete'}:
            raise ValueError('Unsupported checkpoint state')
        raw_plan=resume.get('evidence_plan')
        plan=validate_plan(source,raw_plan,expected['max_batches']) if raw_plan is not None else None
        records=resume.get('batches')
        if not isinstance(records,list) or len(records)>expected['max_batches'] or (records and plan is None):
            raise ValueError('Invalid completed batch count')
        report=copy.deepcopy(expected)
        for index,record in enumerate(records):
            if (index>=len(plan) or record.get('batch')!=index+1
                    or record['evidence']!=[p.model_dump() for p in plan[index]]):
                raise ValueError('Completed evidence differs from frozen plan')
            selection=apply_record(report,record,duplicate)
            if selection!=record['selection']:
                raise ValueError('Checkpoint selections changed')
            report['batches'].append(copy.deepcopy(record))
        if any(report[k]!=resume.get(k) for k in ('facts','questions')):
            raise ValueError('Checkpoint retained items changed')
        if plan is not None:
            report['evidence_plan']=copy.deepcopy(raw_plan)
        if 'retrieval' in resume:
            report['retrieval']=copy.deepcopy(resume['retrieval'])
        # A crash after the terminal checkpoint needs no further inference.
        if resume['state']!='running':
            if resume.get('phase')!='finished':
                raise ValueError('Invalid terminal checkpoint')
            reached=all(len(report[k])>=n for k,n in report['targets'].items())
            if (resume['state']=='needs_review') != reached:
                raise ValueError('Invalid completed targets')
            report=copy.deepcopy(resume)
        return report,plan
    except (KeyError,TypeError,ValueError,StopIteration) as error:
        raise ResumeMismatch('Checkpoint does not match validated source, evidence and policy') from error
