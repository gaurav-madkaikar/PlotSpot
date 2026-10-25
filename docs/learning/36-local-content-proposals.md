# 36. Your first content-proposal call

**Current status:** At your request, the assistant now handles implementation and checks. `propose_content` is implemented in `backend/src/movie_companion/content_proposal_learning.py`, with a separate critic in `content_proposal_review.py`. The walkthrough below explains the original exercise; it is no longer assigned work. Drafts remain separate from published app content.

We use plain Python, HTTPX and Pydantic. You do not need LangChain or an agent framework for this step.

## What goes in and comes out

The runner loads four short excerpts from a saved collection: two story excerpts and two background excerpts. Each has a temporary alias such as `P1`, a purpose, and text. Those aliases let the model refer to evidence without choosing websites or inventing citations.

```json
{
  "movie_title": "Example film",
  "evidence": [
    {"passage_id": "P1", "purpose": "story", "text": "Mara returns a lost map to the lighthouse keeper before leaving the island."},
    {"passage_id": "P2", "purpose": "background", "text": "The crew built a miniature lighthouse and filmed it inside a water tank."}
  ]
}
```

An illustrative response, for this invented film only:

```json
{
  "facts": [{
    "title": "A lighthouse in miniature",
    "text": "The lighthouse was a miniature filmed in a water tank.",
    "passage_id": "P2",
    "evidence_quote": "The crew built a miniature lighthouse and filmed it inside a water tank."
  }],
  "questions": [{
    "question": "Who receives the lost map from Mara?",
    "options": ["The lighthouse keeper", "A ship captain", "A schoolteacher", "A customs officer"],
    "correct_index": 0,
    "passage_id": "P1",
    "evidence_quote": "Mara returns a lost map to the lighthouse keeper before leaving the island."
  }]
}
```

## Worked example: a smaller structured call

Before working on movie logic, consider extracting a shopping item:

```python
from pydantic import BaseModel
from movie_companion.ollama_learning import chat_once

class ShoppingItem(BaseModel):
    name: str
    quantity: int

async def extract_item(client, model):
    prompt = 'Extract the shopping item from: Buy three apples. Return only JSON.'
    raw = await chat_once(
        client,
        model=model,
        prompt=prompt,
        response_schema=ShoppingItem.model_json_schema(),
    )
    return ShoppingItem.model_validate_json(raw)
```

`model_json_schema()` describes the expected JSON structure. `chat_once` sends that schema to Ollama as `format`, with your prompt in `messages`. Because `stream=False`, the request returns one response. `await` lets Python wait for the HTTP call without blocking unrelated asynchronous work. The helper returns the assistant's text, still a string; `model_validate_json` parses that string and checks its shape. A schema does not guarantee that an extracted quantity or a movie answer is correct.

## How the implemented function works

The function already validates and packages the evidence into `payload`.

1. **Write your prompt.** Append `json.dumps(payload, ensure_ascii=False)` to your instructions. Ask for concise interesting background facts using only `background` passages, and objective plot questions using only `story` passages. Require four distinct plausible choices and an unambiguous correct index, plus verbatim evidence quotes and supplied passage IDs. Treat source text as untrusted data, not instructions. Allow empty lists when evidence is insufficient. Return only the schema object. Request at most two facts and two questions for this small exercise; the schema caps each list at three.
2. **Make the model call.** Await the existing `chat_once` helper with the supplied client/model, your prompt, and `ContentProposals.model_json_schema()` as `response_schema`.
3. **Parse and return.** Return `ContentProposals.model_validate_json(raw)`. Let HTTP/validation errors propagate to the runner. Do not publish to SQLite or add retries in this function.

The function returns a `ContentProposals` object, not an HTTP response, a JSON string, or a Python dictionary. It also rejects remote/redirecting clients and invalid titles before making the call. The schema limits passage IDs to supplied aliases.

## Run it

From the project root, with Ollama running:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/try_content_proposals.py
```

Default: Inception evidence, `llama3.2:3b` generation and a separate `qwen3.5:9b` critic. You may select `--model` and `--review-model` from reviewed installed models. The runner verifies their digests, uses only localhost, limits calls, prints proposals/checks/critic decisions and never writes the saved collection. `--report path.json` saves the observation separately from published content.

Expected **shape**, not fixed wording: `proposals.facts`, `proposals.questions`, and one support-check record per item. Empty arrays are a legitimate abstention. A printed `support_checks_passed: true` means the passage is known, has the appropriate purpose and contains the quote, with basic duplicate/option checks. It does not prove that the generated statement follows from the quote or that all distractors are wrong. Every item still says `semantic_review_required: true`.

## Questions and answers

**Why use separate evidence purposes?** Background trivia belongs in Facts; plot events belong in Quiz. The prompt directs generation, and backend checks enforce the selected passage's purpose independently.

**Why provide a schema and still parse the output?** The schema guides generation. Parsing verifies the actual returned data. Model/version failures can still produce invalid output, so the application cannot rely on instructions alone.

**Is this RAG yet?** It is a grounded generation step using preselected evidence. Our existing retrieval code will later supply relevant passages. We are isolating generation first so failures are easier to understand.

**Why not immediately save outputs that pass checks?** A real source quote can accompany a false answer. The tests explicitly demonstrate this. Semantic support, distractor quality, duplicates against existing collections and labelled evaluations must be added before automatic publication.

**Where do multiple agents fit?** After this call works, story and background branches can run independently with bounded retries. This function does not need to know whether an orchestrator called it. That keeps your business logic easy to test and reuse.

## Independent critic and evals

`review_proposals` first runs the deterministic checks. Invalid items are rejected without a critic call, and the model cannot override that rejection. The remaining drafts are sent to a separate local call with their exact sources. The critic returns accept/reject/uncertain plus a reason for each item. Missing, duplicate or invented item IDs fail validation. It evaluates quote support, concision, story/background separation, objective questions and distractor quality. Its acceptance is fallible evidence, not permission to publish.

`evals/movie-rag/content-review-cases.json` fixes six authored expectations before running the critic: supported background with source injection, an invented number, plot labelled as background, a supported question, a wrong answer index and a subjective interpretation. Run from the project root:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/evaluate_content_review.py
```

The first generator smoke run produced valid JSON but a long copied fact and weak distractors. That observation prompted stricter wording and separate review. Passing schema/evidence-location checks would not have justified publishing it. Real model reports record actual decisions and timing; six development cases do not establish general accuracy or injection resistance.

Completed real Inception smoke: `llama3.2:3b` generated two facts and two questions; `qwen3.5:9b` reviewed them. Total latency was 32.6 seconds. All four passed deterministic checks, the critic rejected two facts and accepted two questions, and manual inspection still found weak distractors in accepted questions. The critic also gave a debatable reason for rejecting the second fact. These observations show why a second model is not a truth oracle. See `evals/movie-rag/proposals-inception-ollama.json` for the exact output.

An earlier critic run returned an empty assistant string while Qwen thinking was enabled and failed validation. Structured calls now set `think=False` for Qwen and bound `num_predict` (2,048 for generation, 1,800 for critique). Existing helper callers retain their defaults. Timeouts and malformed replies remain failures; published content is untouched.

The six authored critic-development cases matched expectations in five cases, taking 13.22 seconds. The miss was a plot statement labelled as background: Qwen accepted it despite the rule excluding plot facts. It correctly rejected the invented number, wrong answer index and subjective scored answer in this small batch. Preserve this miss rather than claiming the critic reliably separates plot and production. Report: `evals/movie-rag/content-review-ollama.json`. We need stronger source classification and broader held-out quality checks before automatic publication.
