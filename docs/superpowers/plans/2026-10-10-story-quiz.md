# Story quiz and background facts — source routing

User-approved scope: movie-content quizzes; unusual non-plot facts from Wikipedia and reviewed internet sources. Ship working slices before more isolated exercises.

## Current slice

- Three scored plot/ending questions, plus one explicitly unscored interpretation.
- Reuse learner RAG pipeline; reviewed choices and answer/evidence checks; withhold unsupported questions.
- Separate Facts panel for the real filming cornfield and the production’s secret working title. Wikipedia revision citations; no live-news claim.
- Spoiler consent, bounded calls, partial results, cancellation, replay, source links and existing API validation remain.

## Next source connector slice

1. Preserve article sections when extracting Wikipedia. Tag evidence as plot, production, casting, filming, music, or effects. Quiz retrieval filters plot; Facts retrieval filters background. TMDB overview supplements basic plot context; do not substitute it for detailed scene evidence.
2. Add an explicit movie-to-script mapping for IMSDb. Store title, draft date/version, retrieval date and content hash. Reject mismatched titles and unverified/early drafts from scored questions about the released movie. Interstellar’s inspected IMSDb script is dated March 12, 2008; keep it excluded. Offer a source link rather than republishing the full screenplay.
3. Add bounded read-only adapters for reviewed external article URLs, beginning with primary interviews, studio notes or research institutions. Record publisher, author/date when available, URL and snapshot hash. Do not allow the model to fetch arbitrary URLs or follow private-network redirects. Generalise the currently Wikipedia-only citation contract before rendering other publishers.
4. Extract short, attributed background claims; exclude plot retellings and duplicate basic metadata. Rank for specificity/interest, not sensationalism. Distinguish a reported claim from a verified fact; never invent details when evidence is missing. Separate older production background from dated news.
5. Evaluate wrong-movie retrieval, script-versus-film conflicts, plot leakage into Facts, unsupported questions, duplicate facts, fabricated sources, injection in fetched pages and source failures. Use labelled evidence and human review for relevance/interestingness; schema validation alone cannot measure these.

Future source integration is not implemented by this slice. Current coverage is Interstellar; question selection is curated, explanations use local Ollama. This is not yet a general quiz-generation or autonomous web-research agent.

## Source-routing progress

Item 1 completed in the section-routing slice: heading-aware extraction, section-bounded chunks, Chroma metadata and targeted routing. See `2026-10-10-section-routing.md`. External article adapters and IMSDb provenance remain pending. Existing published starter/expanded collections were retained; new preparation requires classified evidence.
