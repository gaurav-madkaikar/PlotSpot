# 25. Why superhero search missed stored films

## The bug

Search first used a lexical gate: a query word had to appear in the synopsis before the film could reach embedding ranking. `hero movies` therefore missed Batman and Spider-Man descriptions that never used `hero`. It also admitted an ordinary war hero, which was not the user's intended category.

This shows why good embeddings alone cannot fix retrieval: filtering can remove a relevant candidate before the model ever compares it.

## The correction

`search_intent.py` recognizes hero/superhero phrasing as a superhero theme. `theme_support` looks for specific whole character/franchise phrases or explicit superhero terminology in saved titles and synopses. It avoids generic evidence such as `hero`, `power`, or `spider` alone. No movie IDs are hardcoded.

`catalog_search.py` applies the theme alongside genre and explicit UI filters. For a theme-only query, matching theme evidence admits candidates; additional descriptive terms still need synopsis support. Ollama embeddings rank admitted candidates. Exact title/cast matches retain precedence so a film called `A War Hero` can still be found by its name. Theme negation is supported.

## Actual results and limits

The 200-film local catalog returned nine films for both `hero movies` and `superhero movies`, including The Dark Knight, three Spider-Man films, two Avengers films, Batman: Knightfall, Justice League: Starcrossed, and Miraculous World: New York. `hero movies about knitting` returned zero. The backend suite passed 335 checks, and the corrected results were verified in the open browser.

This is a bounded vocabulary correction, not a general understanding engine. An unfamiliar superhero can still be missed; a passing character reference can be misleading. A broader next step is to import TMDB topic keywords, label a larger theme-query evaluation set, and compare hybrid retrieval/reranking against this baseline. Increasing catalog coverage is a separate task: search cannot return films absent from the saved collection.
