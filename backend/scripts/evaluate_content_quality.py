"""Evaluate a frozen development or held-out critic dataset using local Ollama."""
import argparse
import asyncio
import json
from pathlib import Path

import httpx

from movie_companion.content_quality_eval import QualityDataset, evaluate_quality
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion import structured_content_review
from prepare_content_drafts import write_checkpoint


async def main(args):
    if args.dataset.resolve()==args.output.resolve() or args.output.suffix!='.json':
        raise ValueError('Use a separate JSON report')
    if args.dataset.stat().st_size>1_000_000:
        raise ValueError('Dataset file exceeds the input budget')
    dataset = QualityDataset.model_validate_json(args.dataset.read_text())
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                follow_redirects=False, trust_env=False) as client:
        async with asyncio.timeout(30):
            await verify_local_model(client,args.model)
        report = await evaluate_quality(client,dataset=dataset,model=args.model,model_digest=DIGESTS[args.model],
            deadline_seconds=args.deadline_seconds,checkpoint=lambda r:write_checkpoint(args.output,r),
            reviewer_module=structured_content_review if args.verifier=='structured' else None)
    print(json.dumps({'state':report['state'],'partition':report['partition'],
                      'metrics':report['metrics'],'elapsed_seconds':report['elapsed_seconds']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',choices=['llama3.2:3b','qwen3.5:9b'],default='qwen3.5:9b')
    parser.add_argument('--verifier',choices=['baseline','structured'],default='baseline')
    parser.add_argument('--deadline-seconds',type=int,choices=range(1,601),default=360,
                        metavar='SECONDS',help='Overall evaluation deadline (1–600 seconds).')
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError,httpx.HTTPError,TimeoutError,OSError) as error:
        raise SystemExit(f'Quality evaluation failed ({type(error).__name__}). Publications unchanged.') from error
