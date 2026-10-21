"""Create the reproducible writer/critic/readiness ablation report."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from movie_companion.generation_ablation import analyze_generation_exports, render_generation_ablation


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exports", type=Path,
                        default=ROOT / ".cache/expanded20/reviews/approved-final-v3")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "evals/movie-rag/generation-ablation/funnel-v1.json")
    parser.add_argument("--markdown", type=Path,
                        default=ROOT / "evals/movie-rag/generation-ablation/funnel-v1.md")
    args = parser.parse_args()
    if args.output.exists() or args.markdown.exists():
        raise ValueError("Use new output paths; generation ablation artifacts are immutable")
    paths = sorted(args.exports.glob("*.json"))
    report = analyze_generation_exports([(path, json.loads(path.read_text())) for path in paths])
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.markdown.write_text(render_generation_ablation(report))
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()
