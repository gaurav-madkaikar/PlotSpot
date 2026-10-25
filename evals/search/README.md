# Lexical suggestion baseline

Run from the project root: `backend/.venv/bin/python evals/search/run_baseline.py`.

The script writes `report.json`, including the dataset hash, scorer, fixed threshold, aggregate counts, and each case's actual suggestions. It never reads credentials or contacts TMDB. The matching corpus is the ten demo movies and their cast.

`cases.json` contains 20 development cases and 10 designated held-out cases. Cases cover spelling errors, exact inputs that should remain uncorrected, and unrelated queries. This is a small hand-authored regression baseline; do not treat its held-out accuracy as representative of all movies/actors or as an independent benchmark. The fixed threshold is 0.8; no tuning was performed against held-out results.

Measured: development suggestion top-three recovery is 11/12, compared with 0/12 for existing substring search. Held-out recovery is 6/6, compared with 1/6 for substring search. Neither split produced suggestions for unrelated queries (0/5 development, 0/3 held-out), and all four exact queries remained uncorrected. The development miss `Truman Shwo` is retained in the per-case report.

Suggestions point to known labels with source movie IDs. Cast-name labels do not resolve same-name people uniquely, and same-title films remain separate identities in normal search results. Hard filters still apply after the user selects a suggestion. Next evaluations should add larger independently labeled data, ambiguous names, out-of-coverage films, multilingual spellings, and threshold trade-offs without reusing the held-out cases for tuning.
