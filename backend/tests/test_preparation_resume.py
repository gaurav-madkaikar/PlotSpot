import asyncio
import copy
from dataclasses import replace

import pytest

from movie_companion import content_preparation as pipeline
from movie_companion.preparation_resume import ResumeMismatch
from test_content_preparation import source, mock_models


def interrupted(monkeypatch,*,max_batches=2,phase='generating'):
    calls=mock_models(monkeypatch)
    saved=[]
    def checkpoint(r):
        saved.append(copy.deepcopy(r))
        if len(r['batches'])==1 and r['phase']==phase:
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',
                    max_batches=max_batches,checkpoint=checkpoint))
    return calls,saved[-1]


def test_resume_skips_complete_batch_and_keeps_exact_results(monkeypatch):
    calls,saved=interrupted(monkeypatch)
    assert calls==['generate','review']
    r=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',max_batches=2,resume=saved))
    assert calls==['generate','review','generate','review']
    assert len(r['batches'])==2 and r['batches'][0]==saved['batches'][0]
    assert r['facts'][:2]==saved['facts'] and r['questions'][:2]==saved['questions']
    # Counter-based fixture output matches uninterrupted execution.
    mock_models(monkeypatch)
    expected=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',max_batches=2))
    for key in ('batches','facts','questions','state','stop_reason','evidence_plan'):
        assert r[key]==expected[key]


@pytest.mark.parametrize('change',['policy','source','sections','model','budget','plan-text','plan-purpose',
                                  'batch-order','batch-evidence','selection','retained','reviews','publication','legacy'])
def test_incompatible_or_tampered_resume_fails_before_model_calls(monkeypatch,change):
    calls,saved=interrupted(monkeypatch)
    s=source();kwargs={}
    if change=='policy':saved['workflow_sha256']='0'*64
    elif change=='source':s=replace(s,text=s.text.replace('Lena','Lina'))
    elif change=='sections':s=replace(s,sections=(replace(s.sections[0],title='Story'),*s.sections[1:]))
    elif change=='model':kwargs['model']='other'
    elif change=='budget':kwargs['max_batches']=1
    elif change=='plan-text':saved['evidence_plan'][1][0]['text']='A forged passage that is absent from the original source.'
    elif change=='plan-purpose':saved['evidence_plan'][1][0]['purpose']='background'
    elif change=='batch-order':saved['batches'][0]['batch']=2
    elif change=='batch-evidence':saved['batches'][0]['evidence']=saved['evidence_plan'][1]
    elif change=='selection':saved['batches'][0]['selection'][0]['retained']=False
    elif change=='retained':saved['facts'][0]['text']='A forged unrelated retained fact from model memory.'
    elif change=='reviews':saved['batches'][0]['review']['items'].append(saved['batches'][0]['review']['items'][0])
    elif change=='publication':saved['publication_approved']=0
    else:saved.pop('resume_version')
    options={'source':s,'model':'test','review_model':'test','max_batches':2,'resume':saved,**kwargs}
    with pytest.raises(ResumeMismatch):asyncio.run(pipeline.prepare_drafts(None,**options))
    assert calls==['generate','review']


def test_rag_resume_uses_frozen_plan_without_retrieval(monkeypatch):
    from movie_companion.content_evidence_retrieval import RetrievedEvidence
    from movie_companion.proposal_evidence import evidence_batches
    calls=mock_models(monkeypatch);saved=[];loads=[]
    async def load():
        loads.append(True)
        return RetrievedEvidence(evidence_batches(source(),max_batches=2),{'version':'fixture'})
    def checkpoint(r):
        saved.append(copy.deepcopy(r))
        if len(r['batches'])==1:raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',
                    max_batches=2,evidence_loader=load,checkpoint=checkpoint))
    r=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',
                max_batches=2,evidence_loader=load,resume=saved[-1]))
    assert loads==[True] and len(r['batches'])==2
    assert r['retrieval']=={'version':'fixture'}


def test_terminal_checkpoint_replay_makes_no_model_calls(monkeypatch):
    calls=mock_models(monkeypatch)
    r=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',max_batches=1))
    before=list(calls)
    replay=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',max_batches=1,resume=r))
    assert replay==r and calls==before


def test_crash_after_target_checkpoint_finishes_without_more_calls(monkeypatch):
    calls=mock_models(monkeypatch);saved=[]
    def checkpoint(r):
        if len(r['questions'])==10:
            saved.append(copy.deepcopy(r))
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',checkpoint=checkpoint))
    before=list(calls)
    r=asyncio.run(pipeline.prepare_drafts(None,source=source(),model='test',review_model='test',resume=saved[-1]))
    assert r['state']=='needs_review' and calls==before and len(r['batches'])==5
