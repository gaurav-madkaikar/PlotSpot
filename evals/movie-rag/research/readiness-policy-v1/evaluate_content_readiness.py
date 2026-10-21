"""Evaluate readiness controls and replay frozen drafts without publication."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

import httpx

from movie_companion.content_proposals import ContentProposals, EvidenceOrigin, FactProposal, ProposalEvidence, QuizProposal
from movie_companion.content_readiness import fact_readiness, quiz_readiness
from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.evidence_store import SourceDocument
from movie_companion.local_models import DIGESTS
from movie_companion.movie_research import source_loaders
from movie_companion.preparation_jobs import atomic_json
from movie_companion.proposal_evidence import verify_origins
from movie_companion.research_preparation import implementation_hashes
from movie_companion.source_sections import SourceSection


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bank_hash(saved):
    data={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in saved.items()}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def control_fact(case):
    text=case['quote']
    source=SourceDocument('readiness-fiction',329865,text,'Fictional readiness control',
        'https://example.invalid/readiness-control','fiction-v1',
        sections=(SourceSection(0,len(text),'Production','production'),))
    origin=EvidenceOrigin(movie_id=329865,source_id=source.source_id,source_ref=source.source_ref,
        revision=source.revision,section_title='Production',section_category='production',start=0,end=len(text))
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=text,origin=origin)]
    return source,evidence,FactProposal(title=case['title'],text=case['text'],passage_id='P1',evidence_quote=text)


def control_quiz(case):
    proposals=ContentProposals(facts=[],questions=[QuizProposal(question=p['question'],
        options=[p['answer'],'A different fictional detail','Another fictional detail','A fourth fictional detail'],
        correct_index=0,passage_id='P1',evidence_quote='This fictional fixture tests novelty only, not factual support.')
        for p in case['candidates']])
    quiz=SimpleNamespace(items=[SimpleNamespace(question=p['question'],options=[p['answer']]*4,
                                               correct_index=0) for p in case['existing']])
    return proposals,quiz


async def main(args):
    if args.output.exists() or args.output.suffix!='.json':
        raise ValueError('Choose a new JSON report; historical outputs stay intact')
    if args.dataset.stat().st_size>100000 or args.baseline.stat().st_size>500000:
        raise ValueError('Evaluation inputs exceed budgets')
    dataset=json.loads(args.dataset.read_text());baseline=json.loads(args.baseline.read_text())
    if dataset['split']!='development' or len(dataset['facts'])!=7 or len(dataset['quizzes'])!=7:
        raise ValueError('Unexpected fixed readiness dataset')
    if baseline['movie_id']!=329865 or not baseline['saved_bank_unchanged']:
        raise ValueError('Expected frozen nonpublishing Arrival baseline')
    bank=ContentStore(args.database);saved=bank.load(329865);before=bank_hash(saved)
    pinned=json.loads(args.bank_manifest.read_text())['saved_bank_hashes']['329865']
    if before!=pinned:raise ValueError('Saved Arrival bank changed since the frozen baseline')
    story_reader,background_reader=source_loaders(329865,sources=args.sources,article_cache=args.articles)
    story,background=await story_reader(),await background_reader()
    documents={d.source.source_id:d.source for d in (*story.documents,*background.documents)}
    run=baseline['runs'][0]
    manifests={s['source_id']:s for b in run['research']['branches'] for s in b['sources']}
    if set(documents)!=set(manifests):raise ValueError('Frozen source set changed')
    for identifier,source in documents.items():
        if hashlib.sha256(json.dumps(asdict(source),sort_keys=True).encode()).hexdigest()!=manifests[identifier]['sha256']:
            raise ValueError('Frozen source content changed')
    initial=implementation_hashes()
    report={'type':'assistant-authored development controls and consumed-draft regression replay',
        'dataset_sha256':sha(args.dataset),'baseline_sha256':sha(args.baseline),
        'runner_sha256':sha(Path(__file__)),'initial_module_hashes':initial,
        'saved_bank_sha256':before,'model':'qwen3.5:9b','model_digest':DIGESTS['qwen3.5:9b'],
        'controls':[],'replay':{},'published':False,
        'limitations':['No independent quality or safety qualification.',
            'Controls test the readiness layer assuming necessary checks passed.',
            'Replay does not regenerate drafts or compare agent-generation quality.',
            'A ready flag is a fallible inspection observation, never publication authorization.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as output:output.write(json.dumps(report,indent=2)+'\n')
    started=monotonic()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,
                                follow_redirects=False,trust_env=False) as client:
        for case in dataset['facts']:
            began=monotonic();source,evidence,proposal=control_fact(case)
            result=await fact_readiness(client,proposal=proposal,evidence=evidence,source=source,base_eligible=True)
            passed=result['ready']==case['expected_ready'] and not result.get('error_type')
            report['controls'].append({'id':case['id'],'kind':'fact','expected_ready':case['expected_ready'],
                'result':result,'passed':passed,'seconds':round(monotonic()-began,3)})
            atomic_json(args.output,report);print(f"{'PASS' if passed else 'FAIL'} {case['id']}",flush=True)
        for case in dataset['quizzes']:
            began=monotonic();proposals,quiz=control_quiz(case)
            result=await quiz_readiness(client,proposals=proposals,quiz=quiz,
                                       base_eligible=[f'Q{i+1}' for i in range(len(proposals.questions))])
            passed=result['ready_ids']==case['expected_ready_ids'] and result['error_type'] is None
            report['controls'].append({'id':case['id'],'kind':'quiz','expected_ready_ids':case['expected_ready_ids'],
                'result':result,'passed':passed,'seconds':round(monotonic()-began,3)})
            atomic_json(args.output,report);print(f"{'PASS' if passed else 'FAIL'} {case['id']}",flush=True)
        story_result=run['preparation']['branches'][0]['result']
        proposals=ContentProposals.model_validate(story_result['proposals'])
        evidence=[ProposalEvidence.model_validate(p) for p in story_result['evidence']]
        verify_origins(story.documents[0].source,evidence)
        result=await quiz_readiness(client,proposals=proposals,quiz=saved['quiz'],
                                   base_eligible=story_result['eligible_for_review'])
        report['replay']['quiz']={'before':story_result['eligible_for_review'],'after':result['ready_ids'],
                                  'readiness':result}
        fact_result=run['preparation']['branches'][1]['result']
        source_evidence={s['source_id']:[ProposalEvidence.model_validate(p) for p in s['evidence']]
                         for s in fact_result['sources']}
        report['replay']['facts']=[]
        for candidate in fact_result['candidates']:
            identifier=candidate['origin']['source_id']
            evidence=source_evidence[identifier]
            result=await fact_readiness(client,proposal=FactProposal.model_validate(candidate['proposal']),
                evidence=evidence,source=documents[identifier],base_eligible=candidate['eligible_for_review'])
            report['replay']['facts'].append({'id':candidate['id'],'before':candidate['eligible_for_review'],
                                             'after':result['ready'],'readiness':result})
            atomic_json(args.output,report)
    report['summary']={'passed':sum(c['passed'] for c in report['controls']),'total':len(report['controls'])}
    report['seconds']=round(monotonic()-started,3)
    report['code_changed_during_run']=initial!=implementation_hashes()
    report['saved_bank_unchanged']=before==bank_hash(bank.load(329865))
    atomic_json(args.output,report)
    print(json.dumps({'controls':report['summary'],'quiz_after':report['replay']['quiz']['after'],
                     'fact_after':[r['id'] for r in report['replay']['facts'] if r['after']]}),flush=True)
    if report['code_changed_during_run'] or not report['saved_bank_unchanged']:
        raise ValueError('Code or saved bank changed during evaluation')
    if report['summary']['passed']!=14:
        raise SystemExit('Some model controls failed; outputs retained.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=Path('../evals/movie-rag/research/readiness-cases.json'))
    parser.add_argument('--baseline',type=Path,default=Path('../evals/movie-rag/research/arrival-cached-v1.json'))
    parser.add_argument('--sources',type=Path,default=Path('../.cache/source-snapshots'))
    parser.add_argument('--articles',type=Path,default=Path('../.cache/background-articles'))
    parser.add_argument('--bank-manifest',type=Path,default=Path('../.cache/source-snapshots/discussion-retrieval-before.json'))
    parser.add_argument('--database',type=Path,default=DEFAULT_PATH)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
