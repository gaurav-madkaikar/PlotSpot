"""Inspect real script-assisted story generation without publishing new questions."""
import argparse
import asyncio
from pathlib import Path
import json
from time import monotonic

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.evidence_store import SourceDocument
from movie_companion.movie_questions import MovieQuestion, MovieQuestionService, QuestionError
from movie_companion.preparation_jobs import atomic_json
from movie_companion.screenplay_source import SCRIPTS
from movie_companion.story_rag import StoryRag, policy_fingerprint


async def main(args):
    if args.source_snapshot and args.report.resolve() == args.source_snapshot.resolve():
        raise ValueError('Report must not overwrite the source')
    if args.report.suffix != '.json':
        raise ValueError('Use a JSON inspection report')
    story = StoryRag(None)
    if not story.enabled(args.movie_id):
        raise ValueError('Script-assisted story gate is closed')
    report = {'movie_id':args.movie_id,'implementation_sha256':policy_fingerprint(), 'published':False}
    async with asyncio.timeout(300):
        async with httpx.AsyncClient(base_url='https://en.wikipedia.org',timeout=40,trust_env=False,follow_redirects=False) as wiki, \
                   httpx.AsyncClient(base_url='https://imsdb.com',timeout=40,trust_env=False,follow_redirects=False) as scripts, \
                   httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,trust_env=False,follow_redirects=False) as model:
            service = MovieQuestionService(wiki,model)
            service.story = StoryRag(scripts)
            if args.source_snapshot:
                if args.source_snapshot.stat().st_size > 1_000_000:
                    raise ValueError('Source snapshot exceeds budget')
                source = SourceDocument(**json.loads(args.source_snapshot.read_text()))
                if source.movie_id != args.movie_id:
                    raise ValueError('Snapshot movie mismatch')
                service.source_cache[args.movie_id] = (monotonic()+300,source)
                report['source_mode'] = 'reviewed_snapshot'
            else:
                report['source_mode'] = 'live_wikipedia'
            started = monotonic()
            answer = await service.ask(args.movie_id,MovieQuestion(question=args.question,allow_spoilers=True))
            report.update(discussion=answer.model_dump(), discussion_seconds=round(monotonic()-started,2))
            atomic_json(args.report,report)
            print(f'Discussion: {answer.status}',flush=True)
            if args.quiz:
                saved = await asyncio.to_thread(ContentStore().load,args.movie_id)
                if saved is None:
                    raise ValueError('A saved quiz is needed for duplicate checks')
                started = monotonic()
                try:
                    source, passages = await service.load_evidence(args.movie_id)
                    generated = await service.story.quiz(model,source=source,passages=passages,existing=saved['quiz'])
                    report.update(new_questions=[q.model_dump() for q in generated],quiz_seconds=round(monotonic()-started,2))
                    print(f'Accepted new quiz questions: {len(generated)} (not published)',flush=True)
                except (ValueError,httpx.HTTPError,QuestionError) as error:
                    report.update(quiz_error=type(error).__name__,quiz_seconds=round(monotonic()-started,2))
                atomic_json(args.report,report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie-id',type=int,choices=sorted(SCRIPTS),required=True)
    parser.add_argument('--question',required=True)
    parser.add_argument('--source-snapshot',type=Path)
    parser.add_argument('--quiz',action='store_true')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    try:
        asyncio.run(main(args))
    except (ValueError,httpx.HTTPError,QuestionError,OSError,TimeoutError) as error:
        raise SystemExit(f'Story inspection failed ({type(error).__name__}).') from error
