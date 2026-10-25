"""Compose a preregistered cascade from a completed direct/specialist run."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from movie_companion.cascade_benchmark import POLICY, compare_cascade, compose_cascade, render_cascade_report
from movie_companion.orchestration_benchmark import project_relative_path


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.markdown.exists():
        raise ValueError("Use new output paths for the first cascade analysis")
    run_raw = args.run.read_bytes()
    prereg_raw = args.preregistration.read_bytes()
    run = json.loads(run_raw)
    preregistration = json.loads(prereg_raw)
    if preregistration.get("policy") != POLICY:
        raise ValueError("Unknown cascade preregistration")
    if run.get("dataset_sha256") != preregistration.get("dataset_sha256"):
        raise ValueError("Run does not use the preregistered frozen dataset")
    if len(run.get("cases", [])) != 30:
        raise ValueError("Expected the complete 30-case run")
    rows = compose_cascade(run["cases"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "preregistration": project_relative_path(args.preregistration, root=ROOT),
        "preregistration_sha256": sha256(prereg_raw).hexdigest(),
        "source_run": project_relative_path(args.run, root=ROOT),
        "source_run_sha256": sha256(run_raw).hexdigest(),
        "dataset": run["dataset"],
        "dataset_sha256": run["dataset_sha256"],
        "comparison": compare_cascade(run["cases"]),
        "cases": rows,
        "limitations": [
            "Automated exact-phrase labels are reviewed project labels, not fresh independent human judgements.",
            "The local models are nondeterministic enough that another run may differ despite pinned versions and decoding settings.",
            "Thirty cases are too few for a production accuracy or statistical-significance claim.",
            "Cascade latency is composed from separately measured sequential arms and excludes application/network serving overhead.",
            "This consumed v2 holdout cannot be used to tune the next routing policy.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.markdown.write_text(render_cascade_report(report))
    print(json.dumps(report["comparison"], indent=2))


if __name__ == "__main__":
    main()
