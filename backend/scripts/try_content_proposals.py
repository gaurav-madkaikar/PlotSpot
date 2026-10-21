"""Run local content proposals without changing saved collections."""
import argparse
import asyncio
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.content_store import ContentStore
from movie_companion.content_proposals import ProposalEvidence, check_proposals
from movie_companion.content_proposal_learning import propose_content
from movie_companion.content_proposal_review import review_proposals
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.wikipedia_source import MOVIE_ARTICLES


async def main(args):
    saved = ContentStore().load(args.movie_id)
    if saved is None or args.movie_id not in MOVIE_ARTICLES:
        raise ValueError("Prepare a reviewed collection for this movie first")
    evidence = []
    # Small exercise context: two reviewed story and two background excerpts.
    for purpose, items in [('story', saved['quiz'].items[:2]), ('background', saved['facts'].items[:2])]:
        for item in items:
            evidence.append(ProposalEvidence(passage_id=f'P{len(evidence)+1}', purpose=purpose,
                                             text=item.citations[0].excerpt))
    started = monotonic()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,
                                follow_redirects=False,trust_env=False) as client:
        async with asyncio.timeout(250):
            await verify_local_model(client,args.model)
            if args.review_model != args.model:
                await verify_local_model(client,args.review_model)
            result = await propose_content(client,model=args.model,
                movie_title=MOVIE_ARTICLES[args.movie_id],evidence=evidence)
            review = await review_proposals(client,model=args.review_model,proposals=result,evidence=evidence)
    report = {'movie_id':args.movie_id,'generator_model':args.model,'critic_model':args.review_model,
              'elapsed_seconds':round(monotonic()-started,2),'source_manifest':saved['source_manifest'],
              'proposals':result.model_dump(),'checks':check_proposals(result,evidence),
              'review':review.model_dump(),'publication_approved':False,'saved_collection_changed':False}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie-id',type=int,choices=sorted(MOVIE_ARTICLES),default=27205)
    parser.add_argument('--model',choices=[m for m in DIGESTS if not m.startswith('nomic-')],default='llama3.2:3b')
    parser.add_argument('--review-model',choices=[m for m in DIGESTS if not m.startswith('nomic-')],default='qwen3.5:9b')
    parser.add_argument('--report',type=Path)
    try:
        asyncio.run(main(parser.parse_args()))
    except NotImplementedError as error:
        raise SystemExit(f'Exercise not completed: {error}') from error
    except (ValueError,httpx.HTTPError,TimeoutError,OSError) as error:
        raise SystemExit(f'Proposal run failed ({type(error).__name__}). Saved content is unchanged.') from error
