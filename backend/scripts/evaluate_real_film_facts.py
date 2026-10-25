"""Inspect fixed real-film facts locally; never publish or overwrite a prior run."""
import argparse
import asyncio
import json
from pathlib import Path

import httpx

from movie_companion.local_models import verify_local_model
from movie_companion.real_film_fact_eval import load_dataset, evaluate_real_facts
from movie_companion.background_fact_workflow import MODEL
from prepare_content_drafts import write_checkpoint


async def main(args):
    if args.output.exists() or args.output.suffix != '.json':
        raise ValueError('Use a new JSON report path to preserve previous outcomes')
    data = load_dataset(args.dataset, args.snapshots)
    # Reserve exclusively before inference; prevents overwriting another invocation.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as file:
        file.write(json.dumps({'state': 'initializing', 'publication_approved': False})+'\n')
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                follow_redirects=False, trust_env=False) as client:
        try:
            async with asyncio.timeout(30):
                await verify_local_model(client, MODEL)
        except (ValueError, httpx.HTTPError, TimeoutError, OSError) as error:
            write_checkpoint(args.output, {'state': 'initialization_failed',
                'error_type': type(error).__name__, 'publication_approved': False})
            raise
        report = await evaluate_real_facts(client, dataset=data,
            deadline_seconds=args.deadline_seconds,
            generation_only=getattr(args, 'generation_only', False),
            checkpoint=lambda r: write_checkpoint(args.output, r))
    print(json.dumps({'state': report['state'], 'quality': report.get('quality', {}).get('metrics'),
                      'generation': report['generation']['observations']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline-seconds', type=int, choices=range(1, 601), default=360)
    parser.add_argument('--generation-only', action='store_true',
                        help='Inspect generation without repeating the labelled critic challenge.')
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, httpx.HTTPError, TimeoutError, OSError) as error:
        raise SystemExit(f'Real-film evaluation failed ({type(error).__name__}). No publication.') from error
