"""Labelled operational controls and a controlled delayed-read scheduling comparison."""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from statistics import median

from movie_companion.movie_research import (
    ReadFailure, ResearchDocument, ResearchLoad, research_movie, source_loaders,
)
from movie_companion.research_preparation import implementation_hashes
from movie_companion.source_sections import SourceSection

FAULTS = {'none','story-error','background-error','partial-background','wrong-movie',
          'wrong-host','wrong-purpose','wrong-shape','timeout','cancellation'}


async def control(fault, mode, story, background):
    ended=[]
    async def story_read():
        if fault=='story-error':raise ValueError('controlled missing story')
        return story
    async def background_read():
        if fault=='background-error':raise ValueError('controlled missing articles')
        if fault=='timeout':
            try:await asyncio.Event().wait()
            finally:ended.append('background')
        if fault=='partial-background':
            return ResearchLoad(background.documents[1:],
                                (ReadFailure(background.documents[0].source.source_id,'HTTPError'),))
        if fault=='wrong-shape':return {'documents': []}
        if fault in {'wrong-movie','wrong-host','wrong-purpose'}:
            doc=background.documents[0]
            source=replace(doc.source,**({'movie_id':155} if fault=='wrong-movie' else
                {'source_ref':'https://unregistered.example/'} if fault=='wrong-host' else
                {'sections':(SourceSection(0,len(doc.source.text),'Plot','plot'),)}))
            return ResearchLoad((ResearchDocument(source,replace(doc.article,source=source)),))
        return background
    if fault=='cancellation':
        entered=asyncio.Event()
        async def blocked():
            entered.set()
            try:await asyncio.Event().wait()
            finally:ended.append('child')
        task=asyncio.create_task(research_movie(movie_id=329865,story_loader=blocked,
                                               background_loader=blocked,mode=mode))
        await entered.wait();task.cancel()
        try:await task
        except asyncio.CancelledError:
            return {'statuses':['cancelled','cancelled'],
                    'cancelled_children_joined':len(ended)==(2 if mode=='parallel' else 1)}
        raise AssertionError('Cancellation did not propagate')
    result=await research_movie(movie_id=329865,story_loader=story_read,
        background_loader=background_read,mode=mode,branch_seconds=.03,deadline_seconds=1)
    return {'statuses':[b.status for b in result.branches], 'trace':result.trace(),
            'timeout_child_joined':bool(ended) if fault=='timeout' else None}


async def main(args):
    if args.output.exists() or args.output.suffix!='.json':raise ValueError('Use a new JSON report')
    raw=args.dataset.read_bytes();data=json.loads(raw)
    cases=data['cases']
    if (len(cases)!=10 or {c['fault'] for c in cases}!=FAULTS
            or len({c['id'] for c in cases})!=10):raise ValueError('Invalid operational control dataset')
    initial=implementation_hashes()
    readers=source_loaders(329865,sources=args.sources,article_cache=args.articles)
    # Freeze actual parsed cached sources before injecting controlled failures.
    story,background=await readers[0](),await readers[1]()
    if len(story.documents)!=1 or len(background.documents)!=2 or background.errors:
        raise ValueError('Complete frozen Arrival sources are required for these controls')
    report={'dataset_sha256':hashlib.sha256(raw).hexdigest(), 'dataset_version':data['version'],
            'type':'operational controls; no LLM semantic accuracy measured',
            'initial_module_hashes':initial,'cases':[], 'published':False}
    for case in cases:
        for mode in ('sequential','parallel'):
            result=await control(case['fault'],mode,story,background)
            passed=result['statuses']==case['expected']
            if case['fault']=='timeout':passed=passed and result['timeout_child_joined']
            if case['fault']=='cancellation':passed=passed and result['cancelled_children_joined']
            report['cases'].append({'id':case['id'],'mode':mode,'passed':passed,**result})
    timings={'sequential':[],'parallel':[]}
    content=[]
    for iteration in range(6):
        for mode in (('sequential','parallel') if iteration%2==0 else ('parallel','sequential')):
            async def delayed_story():await asyncio.sleep(.015);return story
            async def delayed_background():await asyncio.sleep(.020);return background
            result=await research_movie(movie_id=329865,story_loader=delayed_story,
                background_loader=delayed_background,mode=mode)
            timings[mode].append(result.seconds)
            content.append([[d.source for d in b.documents] for b in result.branches])
    report['controlled_scheduling']={'simulated_delays_seconds':{'story':.015,'background':.020},
        'repeats_per_mode':6,'order':'alternating paired modes','seconds':timings,
        'median_seconds':{mode:median(values) for mode,values in timings.items()},
        'same_sources_all_runs':all(c==content[0] for c in content),
        'limitation':'Injected waiting time demonstrates scheduling; not measured internet or production speedup.'}
    report['summary']={'passed':sum(c['passed'] for c in report['cases']),'total':len(report['cases'])}
    report['code_changed_during_run']=initial!=implementation_hashes()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as output:output.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'summary':report['summary'],'controlled_medians':report['controlled_scheduling']['median_seconds']}))
    if report['summary']['passed']!=20 or report['code_changed_during_run']:
        raise SystemExit('Operational controls failed; report saved.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=Path('../evals/movie-rag/research/cases.json'))
    parser.add_argument('--sources',type=Path,default=Path('../.cache/source-snapshots'))
    parser.add_argument('--articles',type=Path,default=Path('../.cache/background-articles'))
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
