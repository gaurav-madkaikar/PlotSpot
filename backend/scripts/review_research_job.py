"""Export evidence for operator review, then publish an explicit pinned selection."""
import argparse,json
from pathlib import Path

from movie_companion.content_store import ContentStore,DEFAULT_PATH
from movie_companion.preparation_job_store import PreparationJobStore
from movie_companion.preparation_jobs import PreparationJobs,BACKEND
from movie_companion.research_checkpoint import digest,derive
from movie_companion.research_jobs import load_bank
from movie_companion.research_publication import publish_selection


def main(args):
    jobs=PreparationJobStore(args.jobs,validate=PreparationJobs._validate)
    if args.action=='publish':
        if args.selection.stat().st_size>20000:raise ValueError('Selection exceeds budget')
        result=publish_selection(jobs=jobs,bank=ContentStore(args.database),
            selection=json.loads(args.selection.read_text()),sources=args.sources,article_cache=args.articles)
        print(json.dumps(result,indent=2));return
    record=jobs.latest(args.movie_id)
    if record is None or not record.get('report'):raise ValueError('No completed research checkpoint available')
    report=record['report'];saved=load_bank(report.get('base_collection'))
    facts,questions,candidates=derive(report,saved)
    output={'movie_id':args.movie_id,'job_id':record['id'],'state':record['state'],
        'report_sha256':digest(report),'workflow_sha256':report['workflow_sha256'],
        'bank_sha256':report['bank_sha256'],'retained':facts+questions,
        'all_candidates':candidates,'targets':report['targets'],
        'notice':'Inspect complete claims, answer choices, sources and topic novelty before creating a selection. This export is not approval.'}
    if args.output.exists():raise ValueError('Use a new review export path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:f.write(json.dumps(output,indent=2)+'\n')
    print(f"Exported {len(facts)} facts and {len(questions)} questions for explicit review.")


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['export','publish'])
    p.add_argument('--movie-id',type=int,default=329865);p.add_argument('--jobs',type=Path,default=BACKEND/'data/private/preparation-jobs/jobs.db')
    p.add_argument('--database',type=Path,default=DEFAULT_PATH);p.add_argument('--sources',type=Path,default=BACKEND.parent/'.cache/source-snapshots')
    p.add_argument('--articles',type=Path,default=BACKEND.parent/'.cache/background-articles')
    p.add_argument('--selection',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.action=='publish' and args.selection is None:p.error('Publish requires an explicit selection file')
    if args.action=='export' and args.output is None:p.error('Export requires a new output path')
    main(args)
