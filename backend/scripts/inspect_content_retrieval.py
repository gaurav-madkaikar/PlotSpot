"""Save an inspectable local retrieval trace without generating or publishing content."""
import argparse
import asyncio
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.content_evidence_retrieval import MODEL, retrieve_draft_evidence
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.proposal_evidence import evidence_pools
from prepare_content_drafts import write_checkpoint


async def main(args):
    if args.output.resolve() == args.source_snapshot.resolve() or args.output.suffix != '.json':
        raise ValueError('Choose a separate JSON report')
    if args.source_snapshot.stat().st_size > 1_000_000:
        raise ValueError('Source snapshot exceeds the file budget')
    source = SourceDocument(**json.loads(args.source_snapshot.read_text()))
    evidence_pools(source)
    started = monotonic()
    async with asyncio.timeout(args.deadline_seconds):
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                    trust_env=False, follow_redirects=False) as client:
            await verify_local_model(client, MODEL)
            store = await asyncio.to_thread(EvidenceStore, args.evidence_store)
            retrieved = await retrieve_draft_evidence(client, source=source, store=store,
                                                      max_batches=args.max_batches)
    report = {'movie_id': source.movie_id, 'embedding_artifact': {'model': MODEL, 'digest': DIGESTS[MODEL]},
              'elapsed_seconds': round(monotonic()-started, 2),
              'retrieval': retrieved.trace,
              'batches': [[p.model_dump() for p in b] for b in retrieved.batches],
              'publication_approved': False, 'saved_collection_changed': False}
    write_checkpoint(args.output, report)
    print(f"{retrieved.trace['snapshot_state']}: {len(retrieved.batches)} batches, "
          f"{len(retrieved.trace['queries'])} topics, {report['elapsed_seconds']}s. Trace: {args.output}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-store', type=Path, default=Path('data/content-evidence'))
    parser.add_argument('--max-batches', type=int, choices=range(1, 9), default=8)
    parser.add_argument('--deadline-seconds', type=int, choices=range(1, 181), default=120,
                        metavar='SECONDS')
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, httpx.HTTPError, TimeoutError, OSError) as error:
        raise SystemExit(f'Retrieval inspection failed ({type(error).__name__}).') from error
