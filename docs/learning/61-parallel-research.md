# 61. Independent research, parallel reads and serial local models

This slice adds an **internal preparation inspection tool**. It does not change
movie-page behavior or publish new facts/quizzes. The existing public preparation
jobs still use their registered Wikipedia path. The new tool composes actual
source adapters, RAG and writer/critic calls in one inspectable workflow.

## Why two researchers?

Story and production facts need different evidence. A plot paragraph can explain
what Louise discovers; a cinematographer interview can explain how a spacecraft
set was built. Keeping those research roles separate prevents one content type
from quietly becoming evidence for the other.

The story researcher reads a registered section-aware Wikipedia snapshot. The
background researcher reads at most two registered publisher articles. Arrival
currently has reviewed TIME and BFI article adapters. Movies without these
registrations return background unavailable; they do not browse guessed URLs.
Scripts remain in their existing separately qualified workflow.

These researchers are **purpose-specific tools**, not autonomous LLM agents.
They have no planning model, shell, database writer or URL-selection authority.
The existing writer and critic remain model-powered roles. Multiple names alone
do not make a system multi-agent: the useful engineering here is distinct
responsibility, source contracts and orchestration.

## Follow the code

1. [movie_research.py](../../backend/src/movie_companion/movie_research.py)
   defines the research contracts, source loaders and coordinator.
2. [research_preparation.py](../../backend/src/movie_companion/research_preparation.py)
   consumes both research results through existing RAG/generation/review stages.
3. [inspect_movie_research.py](../../backend/scripts/inspect_movie_research.py)
   freezes the comparison context, runs both modes and saves a developer report.

The first file is responsible for source acquisition. The second file is
responsible for model inspection. This separation lets us test scheduling
without invoking a model and inspect content without changing scheduling rules.

## What does `await` do here?

Suppose the story read takes 30 milliseconds and the article read takes 40.
In sequential mode, `await story_loader()` finishes before the background loader
starts. Waiting takes roughly 70 milliseconds.

In parallel mode, both asynchronous tasks start before either is joined:

```python
async with asyncio.TaskGroup() as group:
    group.create_task(run('story', story_loader))
    group.create_task(run('background', background_loader))
```

While one task waits on I/O, the event loop can progress the other. Waiting can
approach 40 milliseconds plus overhead. This is concurrency; it does not mean
Python is executing both CPU-heavy computations at the same instant.

`TaskGroup` provides a join boundary: execution continues after its children
finish or their cancellation is handled. For cached local reads,
`asyncio.to_thread` moves blocking file/parser work off the event loop. Cancelling
the coroutine does not forcibly terminate a thread already doing that read;
those reads remain bounded and read-only. Task cancellation and thread
termination are different guarantees.

The source loader also supports explicit refresh through fixed reviewed HTTPS
adapters, with redirects disabled and existing response-size/identity checks.
The comparison CLI deliberately uses cached sources so network changes cannot
change the evidence between its two arms. It does not refresh or rewrite caches.

## Why aren't the local models running in parallel?

Your local Ollama service shares machine resources. Concurrent model requests
can increase contention, memory pressure and model swapping. This workflow
awaits the story generation/review and then background generation/review in
fixed order. Its model concurrency is one **inside one inspection**.

Another independently launched CLI or live app request can still compete with
it. This is not a machine-wide distributed admission policy. That policy and
multi-user throughput measurements belong to the deployment milestone.

Source acquisition timing and full inspection timing are separate fields.
Parallel reads can reduce waiting without changing generation accuracy. If
model work dominates, the overall speedup may be small or absent. Cached-read
timing must not be advertised as internet performance.

## Where is RAG?

After source acquisition, story inspection uses `retrieve_draft_evidence`: index
or reuse the exact Wikipedia snapshot, embed fixed topic queries, retrieve
complete story units and preserve original source offsets. The helper currently
also builds background-topic retrieval internally; this tool consumes only its
story output. It does not introduce a new retrieval algorithm.

Article inspection uses existing `article_evidence`: index/reuse the registered
article, retrieve a bounded source context and retain complete sentence
provenance. The fact generator selects an allowed complete sentence ID. Quiz
generation stays tied to plot evidence. Both branches retain existing critics
and deterministic checks. Similarity ranks evidence; it does not establish truth.

The joined source plan is revalidated before any model call. Each chosen passage
is checked against its source's text, offsets, movie, revision and section.
A generated instruction cannot add a new fetch, execute code or publish content.
Prompt instructions still treat source text as untrusted, but capability limits
are enforced by the code surrounding the models.

## How do failures behave?

- `complete`: the branch supplies its available registered evidence.
- `partial`: one article fails but another valid article survives.
- `unavailable`: the movie has no registered sources for that role.
- `failed`: an expected source/validation error prevents usable evidence.
- `timed_out`: the branch or overall source deadline expires.

Expected source errors become bounded records with the error type. Exception
messages and response bodies are not written into operational errors. An
unexpected programming failure propagates and cancels its sibling rather than
pretending to be missing data. Caller cancellation also propagates.

Source branches have separate deadlines and a workflow deadline. A completed
story read survives an article timeout. The coordinator never silently retries.
Downstream model inspection also preserves a successful role when the other
fails. Inside background inspection, expected per-article model/retrieval errors
retain the other article's result. A branch deadline aborts that unfinished
inspection; this CLI does not implement durable mid-branch model checkpoints.

## Does an accepted draft become a fact on the movie page?

No. Necessary checks and a model critic can mark it eligible for further review,
but the new coordinator has no publication capability. It never calls
`ContentStore.publish`. Existing saved banks remain the public content source.
Draft JSON is a developer artifact; no consumer draft workspace is added.

Novelty checks compare against saved facts. A researcher can find useful
evidence already represented in the bank; its draft can therefore be rejected
or empty. That is a valid result, not a reason to generate something unsupported
to fill a quota.

## What are the evaluations measuring?

The new fixed operational dataset has ten scenarios, each run in both execution
modes. Labels describe statuses and cleanup: complete inputs, missing story,
missing background, one missing article, wrong movie, unregistered host,
wrong purpose, malformed output, timeout and cancellation. These are deterministic
workflow checks, not twenty questions measuring model understanding.

A separate controlled scheduling run injects 15 ms and 20 ms waits into the two
readers. Six paired runs alternate which mode runs first. This demonstrates
overlapping waits with identical source objects. It is a simulation, not a live
provider benchmark.

The real-model comparison reuses the same frozen Arrival sources, model digests,
prompts, saved-fact baseline and retrieval settings. It compares manifests,
evidence/proposals/reviews and necessary checks, excluding timing/cache-state
noise. A fixed seed does not guarantee identical model outputs on all runtimes.
Neither output equality nor critic acceptance proves semantic correctness.
The real run's fixed order can include indexing/model warm-up bias.

Fresh independently reviewed quality labels are still needed. These controls
test operational behavior; earlier tuned content cases remain development data.

## Reproduce

From `backend`, with the existing private snapshots, registered article caches
and reviewed local model tags installed:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluate_movie_research.py --output ../evals/movie-rag/research/operations-new-run.json
PYTHONPATH=src .venv/bin/python scripts/inspect_movie_research.py --movie-id 329865 --compare --report ../evals/movie-rag/research/arrival-new-run.json
```

Use fresh report paths. Existing outputs are never overwritten. Add
`--order parallel-first` to reverse the real comparison order. Keep evaluated
module files unchanged while inference runs; the reports compare initial and
final hashes. Private source snapshots and vectors are local inputs, while
bounded public reports retain provenance and development observations.

## Actual results and what we learned

- **1,050 backend tests pass**, including thirty new research/inspection checks.
- The ten operational cases pass in both modes: **20/20**. This is workflow
  behavior, not agent semantic accuracy.
- Six controlled paired delayed-read runs have median acquisition durations
  **37.296 ms sequential** and **20.671 ms parallel**, with identical source
  objects. These waits were injected deliberately; they are not provider timings.
- Actual cached Arrival source reads took **10.477 ms sequential** and
  **19.546 ms parallel**. There is no observed acquisition improvement here.
- Real Ollama inspections took **118.141s** and **63.990s** overall. The first
  arm includes index/model warm-up, so this difference cannot be attributed to
  concurrent source reads. Both modes produced identical evidence, proposals,
  critic decisions and eligibility outcomes. Module hashes stayed unchanged.
- Each mode proposed two quiz questions and four facts. Two questions and two
  facts passed necessary code/model eligibility checks. That is not four safe
  items ready for publication.

Assistant source inspection found that both quiz topics already exist in the
saved bank, the second question has awkward wording, and some critic-approved
facts add details not independently supported by their chosen sentence. The
TIME mood-board proposal also uses the explicitly discouraged generic title
Visual Inspiration. The rejected photographer fact has a questionable critic
explanation. These findings remain in `inspection-v1.json`; we did not retune
prompts or relabel the outcomes to make the scheduling result look better.

The new tool does not yet enforce quiz novelty against saved questions. Its
eligible-for-review flag is a necessary-check observation, not a publication
policy. All generated items stay unpublished. The eleven existing banks,
independent script policy and Inception expansion gate are unchanged.

Model token counts are not captured by the existing adapters in this report.
There is no cost/token or production-throughput claim. No frontend source or
public API wiring changed, so this slice required backend checks rather than a
new browser feature test.

Reports and interpretation: [research README](../../evals/movie-rag/research/README.md)
will point to the retained operational, model and source-inspection artifacts.
Next content work is stricter complete-support/novelty gates and independently
reviewed quality cases before integrating this tool into durable public jobs.
