# Complete background citations

The authorized citation fix uses a deterministic English sentence-span helper for both retrieval and quote selection. It preserves exact bytes, protects honorifics, initials, dotted abbreviations and decimal numbers, and skips unfinished fragments. Ambiguous abbreviations remain conservative; this is not a general NLP parser.

Retrieval derives spans from whole source sections and keeps only complete sentences inside the retrieved window. The writer selects short complete sentences. Quote membership is checked independently of the critic at inspection and publication. Publication rechecks the whole source section, so a forged origin cannot turn a clipped fragment into a complete quote.

Existing local models, writer/critic prompts, explicit selection, limits and concurrent-write checks remain. No saved content, story policy or UI changes. The fingerprint includes the new helper: old background reports remain archived and cannot authorize publication with changed code.

Tests cover the Donald H. Hewitt defect, honorifics, decimals, references, headings, unfinished text, window edges and forged origins. Rerun the six consumed development cases with a new report; inspect cached Arrival RAG as integration evidence. Neither run establishes unseen accuracy. Verify all ten saved collections remain unchanged.
