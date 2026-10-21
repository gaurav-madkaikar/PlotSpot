"""Create or score the blinded human review for an orchestration run."""
import argparse
import json
from pathlib import Path

from movie_companion.blind_human_review import build_blind_packet, render_review_form, score_blind_packet
from movie_companion.orchestration_benchmark import load_frozen_dataset
from movie_companion.source_sections import source_chunks


ROOT = Path(__file__).resolve().parents[2]


def passage_lookup(dataset, sources):
    lookup = {}
    snapshots = {record.movie_id: record.snapshot for record in dataset.sources}
    for movie_id, source in sources.items():
        for index, chunk in enumerate(source_chunks(source, **dataset.chunk_settings)):
            lookup[f"{snapshots[movie_id][:32]}_{index:03}"] = chunk.text
    return lookup


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--run", type=Path, required=True)
    create.add_argument("--dataset", type=Path, required=True)
    create.add_argument("--packet", type=Path, required=True)
    create.add_argument("--key", type=Path, required=True)
    create.add_argument("--form", type=Path, required=True)
    create.add_argument("--seed", type=int, default=20261017)
    score = sub.add_parser("score")
    score.add_argument("--packet", type=Path, required=True)
    score.add_argument("--key", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "create":
        if any(path.exists() for path in (args.packet, args.key, args.form)):
            raise ValueError("Use new paths; do not replace an existing blind review")
        report = json.loads(args.run.read_text())
        dataset, sources, _ = load_frozen_dataset(args.dataset, root=ROOT)
        packet, key = build_blind_packet(
            report, passage_text=passage_lookup(dataset, sources), seed=args.seed
        )
        for path in (args.packet, args.key, args.form):
            path.parent.mkdir(parents=True, exist_ok=True)
        args.packet.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n")
        args.key.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n")
        args.form.write_text(render_review_form(packet))
        print(f"Created {len(packet['items'])} blinded reviews in {args.packet}")
        return

    if args.output.exists():
        raise ValueError("Use a new output path for scored human review")
    result = score_blind_packet(json.loads(args.packet.read_text()), json.loads(args.key.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
