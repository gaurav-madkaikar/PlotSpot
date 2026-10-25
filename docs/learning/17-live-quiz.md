# Live feature: story quiz and interesting facts

**Superseded viewing flow:** facts/quizzes now load from persistent collections. See [lesson 18](18-prepared-movie-content.md). This lesson records the earlier on-demand RAG slice.

Pacing update: the user wants visible features sooner. The assistant now ships complete feature slices and saves short explanations afterwards. No new exercise is required before using this feature. Your completed embedding, retrieval and question pipeline remain in place.

## Try it now

Open `http://127.0.0.1:5173/movies/157336`, enable **Watched — allow spoilers**, choose **Quiz**, and click **Build my quiz**. Pick an answer to reveal its explanation and evidence. The score updates immediately; **Play again** clears your choices without regenerating the questions. In **Discuss**, example-question buttons fill the input for an easy Q&A demo.

Only Interstellar has reviewed evidence currently. These are three curated story questions (dust coordinates, Mann’s motive, and the watch message) plus an unscored interpretation, with fixed choices and local-AI answers/explanations grounded in retrieved evidence. They are not a general question-generation agent. News and community posting remain future features. Repeating the quiz uses the same question bank.

## Story versus background evidence

The quiz tests events in the film. Interpretation choices are unscored: the watch may suggest connection, lost time, or a promise. The explanation presents one reading and the scene supporting it, not a definitive hidden message. The reflection reuses the watch question’s evidence, so four items require three model calls.

**News & facts → Load production facts** retrieves production background about the cornfield grown for filming and the secret working title. No plot questions appear here. Both panels currently use the same Wikipedia-backed retrieval pipeline. For these curated questions, an internal reviewed source phrase selects eligible passages before your semantic-ranking code runs. This is a narrow curated-evidence lookup, not a measurement of general retrieval quality. Missing statements leave no evidence and require abstention. The hint is not accepted from browser inputs. The pipeline does not yet filter retrieval by article section. The whole article remains spoiler-unclassified, so both need consent.

Wikipedia plot sections are the current quiz source. TMDB’s overview is useful context but too brief for most scene and ending questions. IMSDb is a planned optional script source: scripts must match the released film and carry a draft/version label. The inspected [Interstellar script](https://imsdb.com/scripts/Interstellar.html) is dated March 12, 2008; it is not accepted as final-film evidence. A script can describe a scene; it cannot establish a director’s intended hidden meaning.

Additional websites are planned for facts, prioritising interviews, studio production notes, and reporting with identifiable authors and dates. Wikipedia is the first working source, not a live internet research agent. See [source routing plan](../superpowers/plans/2026-10-10-story-quiz.md).

## How the feature uses your code

```text
Build my quiz → POST /api/movies/157336/quiz
             → create_quiz in movie_quiz.py
             → existing MovieQuestionService.ask for each curated question
             → your query embedding / retrieval / grounded generation
             → supporting source-statement checks
             → quiz JSON → Zod validation → answer buttons and local score
```

The bank defines correct choices independently of model output. Before showing a question, the service requires an answered result, the expected fact, and cited text containing the reviewed supporting statement. This narrow check fits the reviewed question bank; it is not a general factual-entailment checker. Unsupported items are withheld. If a later question fails, an already verified first question can still appear, with a partial-result message. The whole quiz request has a 180-second deadline.

The browser holds your choices in React state. The API includes the correct index, and the UI reveals it only after selection. This is a casual learning game, not an exam or an anti-cheating system. Changing movies or spoiler permission clears quiz state and aborts pending browser requests. Backend/model work may already be running and can continue until its deadline.

## What changed in the model call?

Previously we asked for JSON in the prompt and validated the returned text. We now additionally send a JSON schema through Ollama's `format` field. For grounded replies, it describes `status`, `answer`, and `citation_ids`, restricts citation values to supplied passage IDs, and forbids extra fields. We still parse and validate the result in Python.

`chat_once` accepts optional `response_schema`; without it, earlier free-text examples retain their original request shape. Structured calls use `options={"temperature": 0, "seed": 7}` to reduce sampling variation. This does not guarantee identical outputs across model/runtime versions or make a wrong answer true. The schema addresses formatting; evidence and abstention checks address separate concerns. See [Ollama's structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs).

The existing dataset and expectations were retained. `evals/movie-rag/structured-output.json` records 3/3 automated passes in one local run, compared with the earlier preserved 2/3 run. Both schema and sampling settings changed, and the sample is tiny; this is a useful development observation, not a controlled causal or broad accuracy claim. The runner now records a hash of the generation boundary too, because schema logic lives there.

## Earlier production-quiz verification (before the story correction)

- 223 backend tests pass, including quiz source support, partial failure, API validation and structured-request settings.
- 20 browser checks pass, covering score, reveal, evidence links, replay, permission changes, errors and existing movie journeys.
- TypeScript and the production build pass.
- A real unmocked browser run generated both quiz items, revealed their source-backed answers, reached 2/2, and successfully answered the instrument question in Discuss.
- Desktop/mobile quiz views were inspected; checked mobile view had no horizontal overflow or browser application errors.

The first browser-suite run had one discovery-page load failure with a Vite SyntaxError; a fresh full run passed all 20. Its root cause was not established, so no code fix or broad stability claim is attributed to the rerun.

The existing six-case fixed-evidence generation suite also passed 6/6 in `evals/grounding/structured-output.json`, including its two injected-source cases. This is one small development run; human claim-support review remains pending and it is not a universal prompt-injection guarantee.


## Story correction verification — 2026-10-10

227 backend checks pass; 21 browser journeys pass; TypeScript/build pass. The real Wikipedia/local-Ollama browser smoke produced all three scored questions plus the unscored reflection, completed 3/3, and retrieved both production facts. It used no response mocks, showed no page errors and no horizontal overflow at 375px. Results are saved in `evals/movie-rag/story-quiz-smoke.json`; desktop/mobile views were inspected.

Initial new prompts abstained on supported evidence, so no quiz was displayed. Narrowing curated evidence alone was insufficient. A shorter evidence-only prompt and a clearer character-motive evidence question enabled this development run. This does not prove general model accuracy. Facts use reviewed short descriptions after verifying the relevant local-AI answer and source passage; they are not automatically discovered unique facts.

The revised six-case generation eval passed 5/6 (`evals/grounding/story-prompt-revised.json`): normal answers, missing evidence, and empty evidence passed. Both source-injection cases ignored the malicious commands, but the case containing a legitimate fact incorrectly abstained. This false refusal remains a known limitation. Earlier reports are preserved; human factual-support review is still needed. Model outputs have no write/action capabilities.
