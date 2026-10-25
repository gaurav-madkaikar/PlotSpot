# Section-aware evidence implementation plan

Approved scope: implement item 1 of the existing story-quiz source-routing plan.

Goal: retain Wikipedia section provenance and prevent story/background evidence from being mixed during preparation and internal targeted retrieval.

Architecture: validated character spans identify section categories; each section uses the existing learner window chunker independently. Discuss keeps access to all sections, while internal quiz/fact requests filter before semantic ranking. Saved viewer reads stay unchanged.

- [x] Extract heading-aware, versioned Wikipedia text with inherited subsection categories.
- [x] Validate contiguous source spans and create chunks that cannot cross section boundaries.
- [x] Persist section metadata in Chroma and include section policy in snapshot fingerprints.
- [x] Route collection preparation and internal quiz/fact requests before matching/ranking.
- [x] Test mixed-section boundaries, unknown headings, inherited headings, invalid spans and persistence; inspect a real article.
- [x] Save a short learning note and verification results. Preserve existing published content and generated additions.

Constraints: no new paid dependencies; do not infer spoiler safety from a heading; unclassified text is available for Discuss but ineligible for targeted story/background generation. Old sectionless snapshots remain readable for prior exercises, but new content preparation requires classified sections. Missing section evidence must fail rather than silently use another section.
