"""Freeze the unresolved saved-quiz replacement scope without publishing content."""

import argparse
import json
from pathlib import Path

from movie_companion.content_store import ContentStore
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_completion import build_completion_manifest


def main(args):
    if args.output.exists():
        raise ValueError("Use a new output path for the frozen manifest")
    source_review = json.loads(args.source_review.read_text())
    evidence_review = json.loads(args.evidence_review.read_text())
    whole_bank_review = json.loads(args.whole_bank_review.read_text())
    manifest = build_completion_manifest(
        source_review,
        evidence_review,
        whole_bank_review,
        ContentStore(args.database),
    )
    payload = manifest.model_dump(mode="json")
    payload["summary"] = manifest.summary
    payload["status"] = "proposal_only"
    payload["published"] = False
    payload["publication"] = {"authorized": False, "database_mutated": False}
    atomic_json(args.output, payload)
    print(json.dumps(manifest.summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--evidence-review", type=Path, required=True)
    parser.add_argument("--whole-bank-review", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/movie-content.db"))
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
