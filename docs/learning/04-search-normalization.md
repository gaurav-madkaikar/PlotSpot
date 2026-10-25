# Pairing slice — prepare text for typo matching

The current API searches TMDB titles and exact actor names. The next extension will offer scored suggestions from a bounded set of known movie/actor identities. Ordinary exact searches remain available through TMDB. Unknown identities must not be invented, and suggestion coverage will be explicit.

## Your function

Implement only `normalize_search_text(text: str) -> str` in `backend/src/movie_companion/search_text.py`.

Behavior:

1. Make case consistent with `casefold()`.
2. Preserve letters and digits, including non-English letters. Replace other characters with spaces; do not join words across punctuation.
3. Collapse consecutive spaces, tabs, and newlines into one space and trim the ends.

Examples:

| Input | Output |
|---|---|
| `  AMY   ADAMS  ` | `amy adams` |
| `Spider-Man: No Way Home` | `spider man no way home` |
| `Dune\t2021\n` | `dune 2021` |
| `  기생충  ` | `기생충` |
| ` --- ` | empty string |

Hints: `str.isalnum()` recognizes letters/digits beyond ASCII. A character loop or comprehension can replace punctuation. `split()` without an argument handles runs of whitespace; joining the resulting words gives consistent spacing.

Run from `backend`:

```sh
.venv/bin/pytest tests/test_search_text.py -q
```

Completed on 2026-10-08: the previously reviewed normalization implementation is connected to the suggestion matcher. The current file had returned to the starter stub; the assistant restored the reviewed implementation during integration. All five normalization cases pass, and the suggestion feature is now active.

## What the assistant completes after review

Add similarity scoring and identity-backed suggestions with measured thresholds, preserve exact-match behavior, retain hard filters after selecting a correction, expose movie/actor types rather than guessing ambiguous identities, and integrate suggestion buttons into discovery. Seed suggestion labels from our known movie IDs and expand from validated movie records; disclose bounded coverage rather than claiming all TMDB names can be corrected. Introduce a labeled baseline before tuning; compare typo success and false-positive suggestions against exact search.

This normalization alone does not turn `Intersteler` into `Interstellar`. The separate matcher compares the normalized query against known normalized labels and decides whether evidence is strong enough to suggest a correction. Semantic recommendations remain a later milestone.

## Concepts and answers to revisit

This exercise originally provided instructions rather than review questions. The following questions explain the choices behind those instructions. The worked example records the implementation reviewed in conversation; it does not establish that the later suggestion feature is already connected.

### 1. Why use `casefold()` rather than only `lower()`?

Both make English uppercase/lowercase text comparable. `casefold()` is intended for Unicode caseless comparison and handles additional cases; for example, `"Straße".casefold()` produces `"strasse"`. Apply the same normalization to queries and candidate labels so formatting differences do not create inconsistent comparisons. Preserve the original movie/actor spelling for display.

### 2. Why replace punctuation with spaces instead of deleting it?

Deleting the hyphen in `"Spider-Man"` produces `"spiderman"`, while replacing it produces `"spider man"`. A space preserves the word boundary. Normalizing both a stored label and a query such as `"Spider Man"` then produces the same representation. This is a deliberate matching policy, not a claim that punctuation is meaningless in every language or title.

### 3. Why use `isalnum()` instead of an ASCII-only expression?

An expression restricted to `a-z` and `0-9` would discard letters from Korean and many other languages. `isalnum()` recognizes Unicode letters and numeric characters. The exercise therefore retains `"기생충"` and the digits in `"Dune 2021"` while replacing punctuation and whitespace with spaces. It does not remove accents or establish equivalence between every visually identical Unicode representation; those would require additional explicit normalization rules and tests.

### 4. How do `split()` and `join()` collapse whitespace?

`split()` with no argument divides text on runs of whitespace and omits empty boundary pieces. `"  amy\t adams\n".split()` gives `["amy", "adams"]`. Joining with `" "` returns `"amy adams"`. By contrast, `split(" ")` uses a literal space separator, can retain empty pieces, and does not itself handle tabs/newlines in the same way.

### 5. How does the reviewed implementation work step by step?

```python
def normalize_search_text(text: str) -> str:
    text = text.casefold()
    text = "".join(char if char.isalnum() else " " for char in text)
    text = " ".join(text.split())
    return text
```

For `"  Spider-Man: 2021\n"`, the intermediate values are:

```text
casefold:             "  spider-man: 2021\n"
replace non-alnum:    "  spider man  2021 "
collapse whitespace: "spider man 2021"
```

The comprehension produces one character or replacement space per input character. The first join assembles those characters; the second join assembles words. The function returns new text and does not alter a movie's display title. An empty or punctuation-only input becomes an empty string.

### 6. Does normalization fix spelling mistakes or perform semantic search?

No. `"Intersteler"` becomes `"intersteler"`; it is still misspelled. A separate matcher compares that normalized text with normalized known labels, scores similarity, and applies a threshold before offering suggestions. Identity-backed candidates prevent the system from inventing movie names or arbitrary IDs. Short/ambiguous inputs require care because many unrelated labels can look superficially similar.

Semantic search addresses a different request, such as “films about isolation in space,” using meaning rather than character similarity. Normalization, typo matching, and semantic retrieval are separate stages with separate evaluation needs.

### 7. What do the five normalization tests prove, and what remains to evaluate?

They check expected behavior for case/repeated spaces, punctuation, tabs/newlines, Korean characters, and punctuation-only input. They do not establish typo recovery quality, candidate coverage, actor disambiguation, or UI integration. A useful additional property is idempotence: normalizing already normalized text should leave it unchanged.

The later labeled search baseline should measure whether the correct identity appears among suggestions, whether unrelated queries produce false-positive suggestions, and how thresholds affect both. A high similarity score alone is not proof that the user intended a particular movie.

## Completed extension — follow a suggestion

1. Discovery starts a separate query keyed by `['suggestions', debouncedQuery]`, calling `/api/search/suggestions?q=...`. Its key omits genre/runtime/language because suggestions are based on the query text, not filtered movie results.
2. `search_suggestions.py` normalizes the query and known title/cast labels with your function. Queries shorter than four normalized characters and exact known labels receive no correction.
3. Python's standard-library `SequenceMatcher` computes a lexical similarity ratio. Candidates at or above 0.8 are sorted deterministically, and at most three are returned. The ratio is not a probability or an LLM judgment.
4. Each suggestion includes its label, movie/actor kind, and source movie IDs. Actor labels are cast names associated with movie IDs, not resolved unique TMDB person IDs; subsequent live person resolution still avoids guessing between same-name actors.
5. The UI offers explicit “Search for…” buttons. Clicking one changes only `q`, preserving hard filters, and runs the normal movie search. It never silently rewrites the query or bypasses a runtime restriction. Exact title searches continue to expose separate same-title movie tiles rather than selecting an arbitrary year.
6. Suggestion failures do not fail the primary movie search. Empty suggestions are hidden, and the visible panel states bounded coverage.

The name index starts from ten known fixture movies and learns successfully validated live `Movie` records. It retains at most 200 movie records, evicting the least recently remembered record. It is in process memory and returns to the seeds after restart. Unlike the ten-minute HTTP response cache, this index is a bounded matching corpus without a TTL; it does not cause additional TMDB requests and does not provide broad catalog coverage. Later semantic-catalog ingestion can improve that coverage.

## Measured baseline

The hand-labeled offline suite has 20 development cases and 10 designated held-out cases. The fixed 0.8 threshold was not changed after inspecting the held-out results. The corpus is exactly the ten seed movies and their cast, so these measurements do not establish performance over live TMDB.

| Split | Typo cases | Existing substring search hits | Correct suggestion in top 3 | Unrelated queries with suggestions |
|---|---:|---:|---:|---:|
| Development | 12 | 0 | 11 | 0 / 5 |
| Held-out | 6 | 1 | 6 | 0 / 3 |

All four exact-query cases received no unwanted suggestions. The missed development query is `Truman Shwo`: omitting “The” and transposing letters falls below the chosen threshold. We retain that miss in the report rather than weakening the threshold after seeing it. This small authored split is a regression baseline, not an independently collected benchmark or an agent safety evaluation.

Reproduce from the project root:

```sh
backend/.venv/bin/python evals/search/run_baseline.py
```

The dataset and per-case report are in `evals/search/cases.json` and `evals/search/report.json`. Verification: 55 backend tests, 16 browser journeys, and the production build passed. Browser coverage includes movie/actor typo selection, filter preservation, mobile overflow, clearing, and optional suggestion failure.

A live TMDB browser check also passed: selecting `Interstellar` from `Intersteler` retained Science Fiction, English, and the 150-minute runtime filter; clearing the runtime filter returned Interstellar. The final build caught a missing `suggestionSchema` export, which was added to the frontend contracts before all checks were rerun. This schema validates the suggestion payload before the UI consumes it.
