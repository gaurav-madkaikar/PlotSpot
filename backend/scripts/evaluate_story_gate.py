"""Evaluate a frozen cross-source policy; enable only after both partitions pass."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.preparation_jobs import atomic_json
from movie_companion.story_rag import BACKEND, policy_fingerprint
from movie_companion.story_verification import MODEL, POLICY, QuizSeed, StoryDraft, StoryDrafts, StoryEvidence, draft_from_seed, review_story, select_script_context
from movie_companion.story_quality_cases import load_real_cases
from movie_companion.movie_quiz import QuizItem
from movie_companion.screenplay_source import SCRIPTS

DATA = BACKEND.parent/'evals/movie-rag/cross-source'


def evaluation_paths(dataset_dir, real_cases):
    """Resolve an immutable dataset family without coupling the runner to v1."""
    paths = [dataset_dir/name for name in ('development.json','reserved.json','adversarial.json')]
    return paths, real_cases


def quiz_qualifications(path, fingerprint):
    if path is None:
        return [], None
    if path.stat().st_size > 1_000_000:
        raise ValueError('Quiz inspection report exceeds budget')
    report = json.loads(path.read_text())
    if (report.get('policy') != POLICY or report.get('model') != MODEL
            or report.get('model_digest') != DIGESTS[MODEL]
            or report.get('implementation_sha256') != fingerprint or report.get('published') is not False
            or report.get('totals',{}).get('errors') != 0 or report.get('totals',{}).get('attempt_errors') != 0):
        raise ValueError('Quiz inspection must match this policy, model and code without errors')
    movies = []
    for record in report['movies']:
        if type(record['movie_id']) is not int or record['movie_id'] not in SCRIPTS:
            raise ValueError('Unknown qualification movie')
        questions = [QuizItem.model_validate(q) for q in record['accepted']]
        if questions:
            movies.append(record['movie_id'])
    return sorted(set(movies)),hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(path, expected_count=8):
    if path.stat().st_size > 100000:
        raise ValueError('Evaluation dataset exceeds budget')
    cases = json.loads(path.read_text())['cases']
    if len(cases) != expected_count or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Unexpected preregistered case count or duplicate IDs')
    for case in cases:
        if type(case['expected_accept']) is not bool or case['mode'] not in ('quiz','discussion'):
            raise ValueError('Invalid expectation')
        StoryDraft.model_validate(case['draft'])
        [StoryEvidence.model_validate(e) for e in case['evidence']]
    return cases


async def partition(client, cases, *, pipeline=False):
    results = []
    for case in cases:
        started = monotonic()
        try:
            async with asyncio.timeout(60):
                draft = StoryDraft.model_validate(case['draft'])
                evidence = [StoryEvidence.model_validate(e) for e in case['evidence']]
                if pipeline:
                    seed = QuizSeed(question=draft.question,answer=draft.answer,wiki_alias=draft.wiki_alias,
                        distractors=[o for i,o in enumerate(draft.options) if i != draft.correct_index])
                    alias = await select_script_context(client,seed=seed,evidence=evidence)
                    draft = draft_from_seed(seed,evidence=evidence,script_alias=alias) if alias is not None else None
                decisions = await review_story(client,drafts=StoryDrafts(items=[draft]),evidence=evidence,mode=case['mode']) if draft is not None else [{'accepted':False,'reason':'Selector found no consistent corroboration.'}]
            observed, error = decisions[0]['accepted'], None
        except (ValueError, httpx.HTTPError, TimeoutError) as exc:
            decisions, observed, error = [], False, type(exc).__name__
        results.append({'id':case['id'],'expected_accept':case['expected_accept'],'observed_accept':observed,
                        'matched': error is None and observed == case['expected_accept'], 'error':error,
                        'seconds':round(monotonic()-started,2), 'decisions':decisions})
        print(f"{case['id']}: {'match' if results[-1]['matched'] else 'mismatch/error'}", flush=True)
    positives = [r for r in results if r['expected_accept']]
    negatives = [r for r in results if not r['expected_accept']]
    metrics = {'total':len(results),'matches':sum(r['matched'] for r in results),
               'positive_total':len(positives),'useful_accepted':sum(r['observed_accept'] and not r['error'] for r in positives),
               'negative_total':len(negatives),'false_approvals':sum(r['observed_accept'] for r in negatives),
               'errors':sum(r['error'] is not None for r in results)}
    passed = (metrics['errors']==0 and metrics['false_approvals']==0
              and metrics['useful_accepted']/len(positives)>=.75)
    return {'passed':passed,'metrics':metrics,'cases':results}


async def main(args):
    fingerprint = policy_fingerprint()
    quiz_movies,inspection_sha = quiz_qualifications(args.quiz_report,fingerprint)
    paths, real_path = evaluation_paths(args.dataset_dir,args.real_cases)
    cases = [load_cases(p, count) for p, count in zip(paths, (8, 8, 4))]
    real_cases = load_real_cases(real_path, snapshots=BACKEND.parent/'.cache/source-snapshots',
                                scripts=BACKEND/'data/private/screenplays')
    if len({c['id'] for group in cases for c in group}) != sum(len(group) for group in cases):
        raise ValueError('Evaluation partitions overlap')
    report = {'policy':POLICY,'implementation_sha256':fingerprint,'model':MODEL,'model_digest':DIGESTS[MODEL],
              'dataset_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              'real_movie_dataset_sha256':hashlib.sha256(real_path.read_bytes()).hexdigest(),
              'quiz_movies':quiz_movies,'quiz_inspection_sha256':inspection_sha,
              'thresholds':{'false_approvals':0,'minimum_useful_acceptance':.75,'errors':0},
              'state':'running','passed':False}
    atomic_json(args.report,report)
    if args.enable:
        atomic_json(BACKEND/'data/private/story-rag-gate.json',
                    {key:report[key] for key in ('policy','implementation_sha256','model_digest','passed','quiz_movies','quiz_inspection_sha256')})
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=60,trust_env=False,follow_redirects=False) as client:
        await verify_local_model(client,MODEL)
        report['development']=await partition(client,cases[0])
        atomic_json(args.report,report)
        if report['development']['passed']:
            report['reserved']=await partition(client,cases[1])
        else:
            report['reserved']={'state':'not_consumed'}
        if report['reserved'].get('passed', False):
            report['adversarial']=await partition(client,cases[2])
        else:
            report['adversarial']={'state':'not_consumed'}
        if report['adversarial'].get('passed', False):
            report['real_movies']=await partition(client,real_cases,pipeline=True)
        else:
            report['real_movies']={'state':'not_consumed'}
    if fingerprint != policy_fingerprint():
        raise ValueError('Implementation changed during evaluation')
    report['passed']=all(report[key].get('passed',False) for key in ('development','reserved','adversarial','real_movies'))
    report['state']='finished'
    atomic_json(args.report,report)
    if args.enable:
        atomic_json(BACKEND/'data/private/story-rag-gate.json',
                    {key:report[key] for key in ('policy','implementation_sha256','model_digest','passed','quiz_movies','quiz_inspection_sha256')})
    print('Gate passed.' if report['passed'] else 'Gate closed. Existing movie flows remain active.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=DATA/'outcome.json')
    parser.add_argument('--dataset-dir',type=Path,default=DATA,
                        help='Directory containing frozen development, reserved and adversarial cases')
    parser.add_argument('--real-cases',type=Path,
                        default=DATA.parent/'story-quality/real-movie-cases.json',
                        help='Frozen pinned real-film case labels')
    parser.add_argument('--enable',action='store_true')
    parser.add_argument('--quiz-report',type=Path,help='Matching successful nonpublishing inspection; only its useful movies qualify for expansion')
    args=parser.parse_args()
    dataset_paths, real_path = evaluation_paths(args.dataset_dir,args.real_cases)
    protected = {path.resolve() for path in dataset_paths}
    protected.add(real_path.resolve())
    if args.quiz_report:
        protected.add(args.quiz_report.resolve())
    if args.report.resolve() in protected:
        parser.error('Report must not overwrite a dataset')
    asyncio.run(main(args))
