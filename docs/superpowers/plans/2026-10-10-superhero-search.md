# Superhero search compatibility fix

Restore the approved semantic discovery behavior for `hero movies`, including superhero films whose synopsis uses character names instead of `hero`.

- [x] Add deterministic superhero query cues and phrase-based evidence in title/synopsis. Support negation and preserve other descriptive terms; never use movie IDs as search rules.
- [x] Apply theme constraints before semantic ranking alongside existing genre/runtime/language constraints. Keep identity precedence and honest empty results.
- [x] Test superhero paraphrases, unrelated ordinary heroes, negation, title evidence, pagination, and explicit filters. Run backend checks.
- [x] Verify actual saved-catalog results through the live API and browser. Record collection limitations and a learning note.

Tradeoff: a bounded vocabulary restores common superhero requests without an LLM router or changing saved embeddings. TMDB keyword enrichment would offer broader theme coverage later, but requires an importer/schema update. This correction does not make all descriptive searches universally reliable.
