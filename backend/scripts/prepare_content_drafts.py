"""Prepare local-model drafts from a source snapshot; published content stays intact."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile

import httpx

from movie_companion.content_preparation import prepare_drafts
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.content_evidence_retrieval import MODEL, retrieve_draft_evidence
from movie_companion.local_models import DIGESTS, verify_local_model
from movie_companion.proposal_evidence import evidence_batches
from movie_companion import structured_content_review


def write_checkpoint(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the separate draft file atomically, preserving the last complete
    # checkpoint if writing is interrupted. This never opens ContentStore.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.draft-', delete=False) as output:
            temporary = Path(output.name)
            json.dump(report, output, indent=2, ensure_ascii=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


async def main(args):
    if args.report.resolve() == args.source_snapshot.resolve() or args.report.suffix != '.json':
        raise ValueError('Choose a separate JSON draft report')
    if args.source_snapshot.stat().st_size > 1_000_000:
        raise ValueError('Source snapshot exceeds the file budget')
    source = SourceDocument(**json.loads(args.source_snapshot.read_text()))
    evidence_batches(source, max_batches=args.max_batches)  # fail before model I/O
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', timeout=120,
                                follow_redirects=False, trust_env=False) as client:
        async with asyncio.timeout(30):
            await verify_local_model(client, args.model)
            if args.review_model != args.model:
                await verify_local_model(client, args.review_model)
            if args.evidence_mode == 'rag':
                await verify_local_model(client, MODEL)
        async def load_evidence():
            store = await asyncio.to_thread(EvidenceStore, args.evidence_store)
            return await retrieve_draft_evidence(client, source=source, store=store,
                                                max_batches=args.max_batches)
        report = await prepare_drafts(client, source=source, model=args.model,
            review_model=args.review_model, max_batches=args.max_batches,
            deadline_seconds=args.deadline_seconds,
            checkpoint=lambda report: write_checkpoint(args.report, report),
            reviewer=structured_content_review.review_proposals if args.verifier=='structured' else None,
            evidence_loader=load_evidence if args.evidence_mode == 'rag' else None)
    print(f"{report['state']}: {len(report['facts'])}/5 facts, {len(report['questions'])}/10 questions; "
          f"{len(report['batches'])} batches, {report['elapsed_seconds']}s. {report['stop_reason']}.")
    print(f'Drafts saved to {args.report}. Published content is unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-snapshot', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    models = [m for m in DIGESTS if not m.startswith('nomic-')]
    parser.add_argument('--model', choices=models, default='qwen3.5:9b')
    parser.add_argument('--review-model', choices=models, default='qwen3.5:9b')
    parser.add_argument('--verifier', choices=['baseline','structured'], default='baseline')
    parser.add_argument('--evidence-mode', choices=['rag', 'sections'], default='rag')
    parser.add_argument('--evidence-store', type=Path, default=Path('data/content-evidence'))
    parser.add_argument('--max-batches', type=int, choices=range(1, 9), default=8)
    parser.add_argument('--deadline-seconds', type=int, choices=range(1, 601), default=600,
                        metavar='SECONDS',help='Overall preparation deadline (1–600 seconds).')
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, httpx.HTTPError, TimeoutError, OSError) as error:
        raise SystemExit(f'Draft preparation failed ({type(error).__name__}). Published content is unchanged.') from error
