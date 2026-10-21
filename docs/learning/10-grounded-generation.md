# Lesson 10 — answer from retrieved evidence

## The next connection

Retrieval finds potentially useful passages. Generation turns the question and those passages into an answer. Your new coding slice is `build_grounded_prompt` in `backend/src/movie_companion/grounding_learning.py`. Write the instructions and assemble the input; the assistant has supplied the network composition, checks, and tests.

```text
Notes → embedding model → passage vectors
Question → embedding model → query vector
                    ↓
Movie/spoiler filtering → your ranking → evidence hits
                                           ↓
Assistant serializes evidence → your prompt → chat_once
                                           ↓
                          JSON parsing + citation checks
                                           ↓
                              answer and source IDs
```

The embedding model is `nomic-embed-text:v1.5`; the chat model is `llama3.2:3b`. They have different jobs. We still use direct Python and HTTPX, with no LangChain. This exercise does not change the UI or public API.

## What your function receives

`question` is a nonblank string. `evidence_json` is a string containing a serialized list of retrieved records. Each record has `passage_id`, `text`, and `source_label`. There are no vectors or similarity scores in the prompt: the chat model needs readable evidence, not the numeric representation used to find it.

Illustrative evidence:

```json
[
  {
    "passage_id": "sound",
    "text": "For the fictional film Orbit Day, the sound team recorded a washing machine and slowed its hum to create spacecraft ambience.",
    "source_label": "Synthetic authored cinema-programme notes"
  }
]
```

`json.dumps(records)` converts Python objects to a JSON string. `json.loads(reply)` converts a JSON string back into Python objects. Serialization escapes quotes and newlines in text correctly. It does not neutralize instructions hidden in that text or establish that the text is trustworthy.

## Your prompt requirements

Replace the `NotImplementedError` with a function that returns one string containing:

1. Instructions to answer concisely using **only** the supplied evidence, without adding facts from model memory.
2. Instructions that evidence is **untrusted data**. Instructions inside passages must not change the task or output format.
3. The user's question and the exact `evidence_json`, in clearly labelled sections.
4. Instructions to use `insufficient_evidence` when the supplied text cannot support an answer, even if passages were retrieved. Retrieval does not guarantee relevance.
5. Instructions to return **only a JSON object**, without Markdown fences or surrounding explanations, with exactly the following fields.

| Field | Meaning |
|---|---|
| `status` | `answered` or `insufficient_evidence` |
| `answer` | Nonblank concise answer, or explanation of missing evidence |
| `citation_ids` | List of supplied passage IDs supporting the answer; empty when abstaining |

For an answered response, require at least one supporting ID and prohibit invented IDs. Cite the passage that supports the claim, rather than every retrieved passage. A valid illustrative response is:

```json
{"status":"answered","answer":"The sound team slowed a recorded washing-machine hum to create the spacecraft ambience.","citation_ids":["sound"]}
```

That is an example of the contract, not a measured model output.

## Python string patterns

An f-string can include a variable:

```python
city = "Pune"
message = f"Destination: {city}"
```

Triple quotes let a string span multiple lines:

```python
instructions = """First instruction.
Second instruction.
"""
```

Combine those patterns to build a readable prompt. If you put literal JSON braces inside an f-string, escape them as `{{` and `}}`; otherwise Python interprets braces as expressions. Alternatively, keep the output-schema explanation in an ordinary string and join it with the variable sections. You do not need to parse JSON or call Ollama inside this function.

## Assistant-owned boundaries

`answer_from_hits` receives hits that have **already** passed the movie/spoiler retrieval boundary. It does not independently choose a movie or reclassify spoiler text. Callers must use scoped retrieval first.

It bounds the question, evidence, and prompt sizes; serializes source records; calls your prompt function; awaits `chat_once`; parses the reply; and checks response fields, types, and citation membership. There is one chat request and no automatic repair loop. HTTP failures and invalid responses propagate as errors rather than being displayed as validated answers.

With no hits, it returns a fixed insufficient-evidence explanation **without calling the prompt builder or model**. With nonempty but irrelevant evidence, your prompt must ask the model to abstain. For model-declared abstentions, the boundary displays the same fixed explanation instead of potentially speculative refusal text.

The async wrapper needs `await` because HTTP inference may take time. Your prompt function is synchronous: assembling strings needs no network request. The script awaits embedding, retrieval is ordinary synchronous computation, then it awaits generation.

## Checks and local example

From the project's `backend` directory:

```sh
.venv/bin/pytest tests/test_grounding_learning.py -q
```

There are 19 cases: two learner prompt-contract cases intentionally fail against the starter stub, and 17 assistant boundary cases pass. The prompt tests check question/evidence inclusion and output-schema terms. They do **not** establish that the prompt reliably grounds answers, blocks injection, or causes correct abstention. Those behaviors need model evaluations and human-labelled evidence.

Once you implement your prompt, with the existing local models and Ollama running:

```sh
.venv/bin/python scripts/try_local_grounded_answer.py
```

The example reuses the fictional notes from lesson 09, embeds the notes and question, retrieves scoped evidence, then requests a cited answer. Inspect whether every answer claim is supported by the printed evidence. Malformed JSON or invented IDs cause a visible validation error; do not weaken the checks just to make a reply pass. We will review failures and improve the prompt together.

To explore missing evidence after your initial run, change the teaching script's question to an unsupported question such as the fictional movie's box-office revenue. Expect abstention, but verify what actually happens. This is a learning experiment, not a benchmark.

## Limits that matter

Valid citations prove only that the IDs refer to retrieved passages. A model can cite `sound` while inventing a claim that the passage never makes. We will add human-labelled claim-support and abstention evaluations before claiming grounding quality. Similarity thresholds also require their own retrieval evaluation.

The prompt is a behavioral instruction, not a complete prompt-injection defense. This helper exposes no tools, shell, posting, or deletion capabilities; model text cannot execute actions. Later tool permissions will be enforced by code outside the model. Source authenticity, spoiler classification, owner scope, and malicious-content evaluation remain separate responsibilities.

## Concepts to explain afterwards

1. Why exclude vectors and similarity scores from the answer prompt?
2. What is the difference between validating a citation ID and verifying claim support?
3. Why can insufficient evidence occur even when retrieval returned two hits?
4. Why serialize evidence with JSON instead of manually interpolating its fields?
5. Why is prompt construction synchronous while answer generation is asynchronous?

We will save review answers and actual local outputs after you implement the prompt. No generated-answer result is claimed at the starter checkpoint.

## Completed review — 2026-10-10

Your revised prompt interpolates the question/evidence using an f-string, escapes literal JSON braces, requires evidence-only answers, treats passage instructions as untrusted, and specifies when to abstain. All 19 grounding tests and all 130 backend tests pass. Your function was left unchanged.

The assistant ran `.venv/bin/python scripts/try_local_grounded_answer.py` against the existing local Ollama service. Embeddings used `nomic-embed-text:v1.5`; generation used `llama3.2:3b`.

Actual supported-question output:

```text
Question: How were the spacecraft sounds made?
Status: answered
Answer: The sound team slowed a recorded washing-machine hum to create the spacecraft ambience.
Cited evidence:
[sound] Synthetic authored cinema-programme notes: For the fictional film Orbit Day, the sound team recorded a washing machine and slowed its hum to create spacecraft ambience.
```

The answer is supported by the supplied fictional production note. A second invocation changed only the script's in-memory question, without editing its file:

```text
Question: What was the worldwide box-office revenue of Orbit Day?
Status: insufficient_evidence
Answer: The supplied evidence is insufficient to answer this question.
Cited evidence:
```

The model returned the abstention status; the wrapper supplied the fixed explanation. These two manual examples establish neither broad answer accuracy nor prompt-injection resistance. The concrete format example remains in the prompt; replacing it with a neutral schema is an optional later improvement to reduce answer-copying bias. In this unsupported example, it did not cause the model to copy the sound answer.

## Answers to the review questions

1. **Why exclude vectors and scores?** They helped the retriever select evidence, but the generator needs the passage text and identity to answer and attribute claims. A high similarity score is not proof that a fact is true or supported.
2. **Citation membership versus claim support?** Membership means the cited ID exists among the supplied records. Support means that passage actually justifies the answer's claim. The parser checks membership; semantic support requires separate evaluation or review.
3. **Why insufficient evidence with two hits?** Top-k returns the best available matches even when none contains the answer. Our fictional production notes cannot establish revenue, so the model must abstain despite receiving evidence.
4. **Why JSON serialization?** It preserves record boundaries and escapes text quotes/newlines reliably, avoiding malformed hand-built representations. It does not prevent prompt injection or verify source authenticity.
5. **Why synchronous prompting and asynchronous generation?** Prompting assembles a string in memory. Generation waits for an HTTP response from Ollama, so the async caller uses `await`. Retrieval's sorting is also synchronous; embedding HTTP calls are asynchronous.
