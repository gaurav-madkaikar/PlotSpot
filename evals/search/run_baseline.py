"""Run the fixed lexical baseline on offline labels; never accesses TMDB."""
import hashlib
import json
from pathlib import Path

from movie_companion.catalog import load_catalog, search_movies
from movie_companion.search_suggestions import SuggestionIndex
from movie_companion.search_text import normalize_search_text

folder = Path(__file__).resolve().parent
dataset = folder / "cases.json"
cases = json.loads(dataset.read_text())
index = SuggestionIndex(load_catalog())
outcomes = []
for case in cases:
    suggestions = index.suggest(case["query"])
    row = {**case, "suggestions": [item.model_dump() for item in suggestions.items]}
    if case["category"] == "typo":
        row["top3_hit"] = any(item.label == case["label"] and item.kind == case["kind"] for item in suggestions.items)
        baseline_movies = search_movies(case["query"])
        row["exact_baseline_hit"] = any(
            normalize_search_text(case["label"]) in
            ([normalize_search_text(movie.title)] if case["kind"] == "movie" else
             [normalize_search_text(name) for name in movie.cast]) for movie in baseline_movies)
    else:
        row["unwanted_suggestion"] = bool(suggestions.items)
    outcomes.append(row)

summary = {}
for split in ["dev", "holdout"]:
    rows = [row for row in outcomes if row["split"] == split]
    typos = [row for row in rows if row["category"] == "typo"]
    negatives = [row for row in rows if row["category"] == "negative"]
    exact = [row for row in rows if row["category"] == "exact"]
    summary[split] = {
        "cases": len(rows), "typo_cases": len(typos),
        "exact_baseline_hits": sum(row["exact_baseline_hit"] for row in typos),
        "suggestion_top3_hits": sum(row["top3_hit"] for row in typos),
        "negative_cases": len(negatives),
        "negative_false_suggestions": sum(row["unwanted_suggestion"] for row in negatives),
        "exact_cases": len(exact),
        "exact_unwanted_suggestions": sum(row["unwanted_suggestion"] for row in exact),
    }
report = {
    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
    "threshold": 0.8, "candidate_movies": len(index.movies),
    "scorer": "Python difflib.SequenceMatcher ratio, autojunk=False",
    "scope": "Offline ten-film seed and cast; small hand-labeled suite, not all TMDB",
    "summary": summary, "outcomes": outcomes,
}
(folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(summary, indent=2))
