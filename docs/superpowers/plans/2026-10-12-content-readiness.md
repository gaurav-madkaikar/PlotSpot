# Content readiness checks

**Goal:** Withhold fact drafts whose selected citation does not support the whole
claim and quiz drafts that repeat saved topics or need wording edits.

**Architecture:** Add a separate readiness layer to the internal research
inspector. Necessary provenance/critic checks remain; readiness cannot override
their rejection. Fact checks use the selected complete sentence only, a
source-local name check and the existing evidence-first support reviewer. Quiz
checks compare each stem/correct answer against all bounded saved question/answer
pairs and earlier candidates, with strict IDs. New topics receive a separate
wording review; a narrow incomplete how/revealed-to-be stem check withholds first.
No cosine threshold declares an item novel or a claim true. No publishing or UI
wiring is added in this slice.

**Alternatives:** Wording-only deduplication misses topic paraphrases; allowing
the whole retrieved paragraph in final fact review hides citation gaps. A
separate single-citation and topic review provides inspectable withholding.
Model verdicts remain fallible, and new assistant-authored controls are development
data, not an independent quality holdout.

**Constraints:** Inline execution under continuing user authorization. Preserve
shared saved banks, existing public quiz expansion/script policies and previous
reports. Local calls stay serial, with no retries/tools/publication authority.
At most three quiz candidates and forty saved question/answer pairs; at most
four fact candidates. At most two quiz review calls per batch; at most one
general and two explicit-purpose support calls per eligible fact. Purpose routing
is a bounded English verb heuristic. Unknown IDs, missing reviews and schema
failures withhold. Preserve all earlier failed model runs and unchanged labels.

- [x] Archive Lesson 61 inspection modules and freeze new quote/novelty controls
  before model outcomes. Keep historical labels/reports unchanged.
- [x] Add `quiz_novelty.py`: exact duplicate fast path, bounded full-bank
  question/answer review, within-batch topic checks, clarity assessment and
  strict decision/ID validation. Test ambiguity, wrong IDs, schema limits,
  exact duplicates, differing facts with the same answer and cancellation.
- [x] Add `content_readiness.py`: complete selected citation, known generic-title
  and source-local name checks, evidence-first support review with that quote
  only. Combine readiness with necessary code/critic checks, preserving drafts
  and operational errors. Test no acceptance override or fallback acceptance.
- [x] Integrate the new checks into internal research preparation, track policy
  and module fingerprints, and add a nonpublishing frozen-draft replay/evaluation
  script. Compare eligibility against preserved Lesson 61 drafts without changing
  generation inputs or prompts. Run actual local Ollama controls and replay.
- [x] Run backend checks, inspect actual model failures, verify bank/script
  preservation and write Lesson 62/README/checklist/progress with reproduction,
  measured results and remaining quality limitations.
