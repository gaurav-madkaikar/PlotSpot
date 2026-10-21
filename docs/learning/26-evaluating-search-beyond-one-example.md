# 26. Evaluate search beyond a single example

## What we changed

The search view now shows only the number of films returned on the current page, with the query when present. Collection size, discovery source, and catalog limitation notes were removed from this view. Pagination still shows the page number and total pages. Provider attribution remains in About/footer.

## What an evaluation checks

For `a girl trapped in a world of spirits`, we label Spirited Away as an expected relevant film before executing search. We then inspect its position in the returned IDs. We do not require the entire response to match a fixed sentence or list exactly.

- Hit@5: did at least one expected film appear in the first five results?
- Hit@20: did one appear on the first page?
- Labelled-target recall@20: how many of the example relevant IDs were recovered? This matters when a query has multiple expected films.
- MRR@20: average of 1 divided by the first relevant rank; a missing film scores zero.
- Empty correctness: did requests with no valid matches return zero results?
- Constraint violations: did a returned film break a labelled genre expectation or explicit runtime/language/genre filter?

A cosine score is used to order candidates. It is not the expected answer and is not automatically a calibrated relevance probability.

## What the local run taught us

The app hit 26/38 positive cases in the top five and 27/38 in the top twenty. It correctly abstained on five negative cases. All eleven top-twenty misses excluded their expected candidates before ranking, while raw vectors recovered eight of them. Theme and mood searches remain weak. A passing backend test suite verifies implementation behavior; it does not establish good semantic relevance.

The raw embedding baseline found more targets but returned results for unsupported queries and violated labelled genre constraints. This reveals a recall-versus-abstention tradeoff. Removing every filter is not a complete solution, and adding aliases for each failed example will overfit.

## How to read and rerun the experiment

Use `evals/discovery/README.md` for metrics, reproduction, and limitations; inspect `broad-cases.json` for labels and `broad-ollama-report.json` for actual outputs. The runner calls the shipped search service and local Ollama model. It checks the saved collection fingerprint first. Unit checks independently verify metric arithmetic.

The current 43 cases are development examples with incomplete relevance labels. We cannot claim precision, production accuracy, or an unbiased benchmark from them. Preserve this baseline, make a retrieval improvement, rerun it, and then validate on a new held-out set without tuning to those new examples.
