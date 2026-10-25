# 53. Evidence context and factual precision

A valid quotation does not make every paraphrase true. If a source says a director used musicians' names to remember **character names**, saying it helped remember **roles** changes the claim. If a passage calls someone Johnson, expanding that to Rian Johnson uses knowledge outside the supplied evidence, even if the full name is correct elsewhere.

## What the pipeline checks

The background writer in `background_fact_workflow.propose_article_facts()` selects a complete source-sentence ID. Code attaches the exact quotation. Its instructions now emphasize preserving actions, their objects, qualifiers and causal relationships, and avoiding full-name expansion from memory. Instructions influence generation; they do not guarantee compliance.

The existing local semantic critic still checks the whole claim and heading. `background_fact_review.review_proposals()` adds a separate code check: capitalized multiword names in the factual body must appear in its supplied passage. Registered movie titles are allowed because their identity is already verified. The assessment stores both the model judgment and missing mentions. A missing name produces uncertain, so the candidate is withheld without asserting that it is false.

This is deliberately narrow capitalization logic, not a complete named-entity system. Single names, aliases, other scripts and unusual capitalized phrases need better coverage. A source can contain a name and still fail to support an attribution; the semantic reviewer must check that relationship. The critic can also make mistakes.

## Why retrieval context matters

An isolated sentence might say “he wanted diffuse light,” while the previous sentence identifies who “he” means. `article_evidence()` can prepend one complete preceding sentence from the same source section, provided the entire context remains at most 600 characters. It preserves exact offsets and records `preceding_context_added` in the trace.

This helps resolve identity without asking the model to guess. It does not permit merging unrelated claims: the chosen supporting sentence and supplied context still need to support the whole fact.

## A failed experiment is useful evidence

We tried a more elaborate critic that separately labelled names, meaning, qualifiers and usefulness. Two versions rejected all six supported controls. Rejecting every fact would avoid false acceptance while making the feature useless, so those versions were abandoned and their results preserved.

Retaining the existing semantic critic plus the narrow code check worked better on this development set. A generated-fact run then found another bug: headings such as “Shot Construction” were mistaken for names. The final guard checks factual bodies; heading support remains the semantic critic's responsibility. Regression checks also cover registered titles beginning with The.

## How to read the evaluation

The frozen precision dataset has six supported claims, eight distortions and four missing-name claims over previously inspected source excerpts. The original critic matched 14/18 labels, accepted all six supported claims and wrongly accepted two claims needing more context. The third variant matched 18/18, accepted all six controls and withheld all twelve negatives or missing-context claims.

After correcting the heading bug, the final deterministic replay still matches 18/18. That replay reuses the third variant's actual model judgments and recomputes the code check: it makes **zero new model calls**. Fresh final generation is reported separately. These are consumed, assistant-authored development cases, not an independent accuracy benchmark or proof of safe catalog-wide generation.

Reports and inspected generation outcomes are in `evals/movie-rag/real-film-facts/precision-*`. Cached publisher retrieval is evaluated separately under `evals/movie-rag/background-articles/`. Publication requires a source/policy-pinned inspection and explicit selection; an accepted model judgment alone cannot publish content.

## Questions to revisit

**Why not just improve the prompt?** Prompts can reduce errors but cannot enforce source-local spelling or complete citations. Deterministic checks give repeatable boundaries; semantic meaning still needs an imperfect reviewer and inspection.

**Why is a missing name uncertain rather than false?** The supplied evidence is insufficient. The name may be correct elsewhere, but the system has not established it from this context.

**Why measure useful acceptance as well as false acceptance?** A reviewer that rejects everything has no false approvals and no useful output. Both measures are necessary.

**Do passing tests prove factual accuracy?** Tests verify boundaries, decision mapping, malformed responses and preservation. Labelled model evaluations check observed behavior on specific cases. Neither proves all future facts are correct.

**Where does RAG improve here?** Retrieval can include the exact preceding sentence needed to resolve an identity, and the source check prevents the generator from silently supplying that identity from memory.

## Final inspected outcomes

Fresh final generation produced seven candidates across six films in 110.17 seconds, with four passing automated eligibility and no errors. Inspection supported three; it withheld the causal expansion and copied text, flagged a likely Dune false rejection and required clearer Knives Out wording. Cached TIME/BFI Arrival RAG took 53.59 seconds, returned four candidates/two eligible and reused both article and vector snapshots. Inspection still found combined-claim evidence, generic headings and copy-editing limitations; no new content was published.

All 837 backend checks pass. Hashes confirm preservation of all ten saved movie-content banks and the story/quiz policy. Next work is persistent background jobs so long preparation can recover after restarts, followed by broader reviewed sources and independently labelled quality checks.
