"""Recover bounded story evidence for the seventeen unsupported quiz targets."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

import httpx

from movie_companion.catalog_store import CatalogStore, DEFAULT_PATH as CATALOG_PATH
from movie_companion.movie_source_corpus import MovieSourceCorpus
from movie_companion.movie_web_sources import MovieIdentity
from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_completion import (
    load_completion_manifest,
    load_intent_contracts,
)
from movie_companion.quiz_replacement_evidence import (
    retrieve_replacement_evidence,
    targeted_story_query,
)
from movie_companion.research_checkpoint import digest
from movie_companion.web_corpus_store import WebCorpusStore, DEFAULT_PATH as CORPUS_PATH


POLICY = "quiz-replacement-evidence-recovery-v1"


async def recover_target(corpus, store, movie, target, intent, *, revision):
    before, before_trace = retrieve_replacement_evidence(
        store, target, intent=intent, limit=8
    )
    acquisition = {
        "attempted": True,
        "revision": revision,
        "query_sha256": None,
        "trace": None,
        "error_type": None,
    }
    query = targeted_story_query(movie, intent, revision=revision)
    acquisition["query_sha256"] = digest(query)
    try:
        result = await corpus.targeted_story(movie, query)
        acquisition["trace"] = result.trace
    except (ValueError, OSError, TimeoutError, httpx.HTTPError) as error:
        acquisition["error_type"] = type(error).__name__
    after, after_trace = retrieve_replacement_evidence(
        store, target, intent=intent, limit=8
    )
    return {
        "movie_id": target["movie_id"],
        "title": target["title"],
        "question_id": target["question_id"],
        "old_question": target["old_question"],
        "replacement_brief": target["replacement_brief"],
        "intent": intent.model_dump(mode="json"),
        "evidence": after,
        "retrieval_before": before_trace,
        "retrieval": after_trace,
        "acquisition": acquisition,
        "local_evidence_count": len(before),
    }


async def run(args):
    if args.output.exists():
        raise ValueError("Use a new evidence-recovery output path")
    if args.revision not in (1, 2):
        raise ValueError("Only an initial and one revised query are allowed")
    manifest = load_completion_manifest(args.manifest)
    contracts_payload = json.loads(args.contracts.read_text())
    contracts = load_intent_contracts(args.contracts, manifest=manifest)
    targets = [item for item in manifest.items if item.lane == "evidence"]
    if len(targets) != 17:
        raise ValueError("Evidence recovery requires exactly seventeen targets")

    store = WebCorpusStore(args.corpus)
    catalog = CatalogStore(args.catalog)
    corpus = MovieSourceCorpus(store=store)
    identity = {
        "policy": POLICY,
        "manifest_sha256": digest(manifest.model_dump(mode="json")),
        "contracts_sha256": digest(contracts_payload),
        "revision": args.revision,
        "planned": len(targets),
    }
    report = {
        **identity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "published": False,
        "items": [],
        "publication": {"authorized": False, "database_mutated": False},
    }
    atomic_json(args.output, report)
    try:
        for item in targets:
            target = {
                **item.model_dump(mode="json"),
                "evidence": {"explanation": item.replacement_brief},
            }
            try:
                movie_record = catalog.get_movie(item.movie_id)
                if movie_record is None:
                    raise ValueError("Movie metadata is unavailable")
                row = await recover_target(
                    corpus,
                    store,
                    MovieIdentity.from_movie(movie_record),
                    target,
                    contracts[item.question_id],
                    revision=args.revision,
                )
                row["error_type"] = None
            except (ValueError, OSError, TimeoutError, httpx.HTTPError) as error:
                row = {
                    "movie_id": item.movie_id,
                    "title": item.title,
                    "question_id": item.question_id,
                    "old_question": item.old_question,
                    "replacement_brief": item.replacement_brief,
                    "intent": contracts[item.question_id].model_dump(mode="json"),
                    "evidence": [],
                    "retrieval_before": None,
                    "retrieval": None,
                    "acquisition": None,
                    "local_evidence_count": 0,
                    "error_type": type(error).__name__,
                }
            report["items"].append(row)
            atomic_json(args.output, report)
    finally:
        await corpus.close()

    report["status"] = "proposal_only"
    report["summary"] = {
        "targets": len(report["items"]),
        "targets_with_evidence": sum(bool(item["evidence"]) for item in report["items"]),
        "acquisition_errors": sum(item["error_type"] is not None for item in report["items"]),
        "new_sources_accepted": sum(
            ((item.get("acquisition") or {}).get("trace") or {}).get(
                "accepted_web_pages", 0
            )
            for item in report["items"]
        ),
    }
    atomic_json(args.output, report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--revision", type=int, required=True, choices=(1, 2))
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
