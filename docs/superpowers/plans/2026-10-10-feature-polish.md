# Feature polish and explicit quiz expansion

User-authorized scope: redesign Facts/Quiz with ui-ux-pro-max, concise copy, no evidence drawer after correct answers, option-letter feedback after incorrect answers, and Generate more questions below the quiz.

Implemented direction: charcoal/gold quiz with compact sans headings and two-column desktop question grid; ivory numbered facts in a responsive editorial grid. Retain semantic groups, keyboard controls, sources for wrong answers/reflections/facts, attribution, spoiler gating, saved starter content and local answer selections.

Expansion path: explicit POST /quiz/more → local Ollama structured proposals against saved plot excerpts → validate schema, exact quoted evidence, correct-option occurrence, known passage IDs, distinct choices, duplicate/near-identical wording → append accepted questions and persist atomically using a publication timestamp check. No source fetch or arbitrary network tools. Cap three proposals/request, 90-second deadline, shared single model slot, forty items total. Unsupported proposals are omitted; if none pass, the saved quiz remains unchanged. Preserve choices when new questions arrive.

Limitations: quotation/option membership is not a general entailment proof, lexical similarity does not detect every paraphrased duplicate, and no automated checker proves all distractors wrong. Generated questions need content-quality evals/human review. The reviewed starter bank remains distinct from generated additions. Content generation does not imply universal coverage beyond Interstellar.
