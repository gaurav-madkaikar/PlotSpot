# Bounded movie research

Continue the approved agent-orchestration milestone with two purpose-specific
research branches in the internal preparation tools. Story reads the registered
Wikipedia snapshot; background reads up to two registered publisher snapshots.
Parallel mode overlaps read-only source acquisition, with sequential mode using
the same loaders as its baseline. Model-based retrieval, drafting and review
remain serial on the local Ollama service. No account, UI or publishing feature
is added, and no unregistered URLs or scripts are introduced.

Each branch returns validated sources, bounded operational errors and timing.
An expected source error affects its branch; a second usable article survives
the failure of the first. A global deadline preserves completed branches and
joins cancelled work. Caller cancellation propagates and joins children.
Unexpected programming failures propagate instead of masquerading as missing
data. Stable source order is independent of task completion order.

Downstream story generation uses existing Wikipedia RAG and structured quiz
review. Background generation uses existing article RAG and fact inspection.
All origins are revalidated; a researcher cannot promote a production article
to story evidence. Reports are nonpublishing developer artifacts. Saved movie
banks and existing HTTP preparation jobs are unchanged in this bounded slice.

Compare both execution modes on identical frozen Arrival sources and model
digests. Report source/evidence/output equality and separate acquisition from
total latency. Controlled delayed-reader tests demonstrate scheduling, not live
internet performance. Labelled operational scenarios cover partial failures,
identity/purpose rejection, timeouts and cancellation; they are not a semantic
accuracy benchmark. Existing model reviewers remain fallible and fresh
independently reviewed quality labels remain pending.

Alternatives: parallel model generation risks local resource contention;
parallel CPU-only ranking offers little benefit. Parallel independent reads are
the useful initial boundary. Python asyncio is sufficient; introducing an agent
framework would not change the safety or concurrency contract.

Learning: specialist roles versus autonomous agents, task concurrency versus
model concurrency, fan-out/join, partial results, cancellation, provenance and
fair scheduling comparisons. User's continuing authorization covers inline
implementation and checks; no additional exercise, delegation or commit.
