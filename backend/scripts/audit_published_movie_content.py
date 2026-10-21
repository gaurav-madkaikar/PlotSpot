"""Audit reviewed movie publications and emit machine/human-readable reports."""
import argparse
import json
from pathlib import Path

from movie_companion.content_store import ContentStore, DEFAULT_PATH
from movie_companion.published_content_audit import audit_published_content, render_markdown


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    temporary.replace(path)


def main(args):
    if args.audit.stat().st_size > 1_000_000 or args.receipts.stat().st_size > 1_000_000:
        raise ValueError("Audit input exceeds budget")
    review = json.loads(args.audit.read_text())
    receipts = json.loads(args.receipts.read_text())
    report = audit_published_content(review_audit=review, publication_log=receipts,
                                     bank=ContentStore(args.database))
    write(args.json_output, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write(args.markdown_output, render_markdown(report))
    print(json.dumps({"status": report["status"], "movie_count": report["movie_count"],
                      "metrics": report["metrics"]}, indent=2))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=root / "evals/movie-rag/expanded-20/final-review-audit.json")
    parser.add_argument("--receipts", type=Path, default=root / "evals/movie-rag/expanded-20/publication-receipts.json")
    parser.add_argument("--database", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--json-output", type=Path, default=root / "evals/movie-rag/expanded-20/published-content-audit.json")
    parser.add_argument("--markdown-output", type=Path, default=root / "evals/movie-rag/expanded-20/published-content-audit.md")
    try:
        main(parser.parse_args())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Published-content audit failed ({type(error).__name__}): {error}") from error
