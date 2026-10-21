# Purpose-specific generation implementation plan

Execute inline under the user's approved RAG scope and assistant-owned coding preference.

**Goal:** Prevent background passages from becoming quiz inputs by separating generator calls.

**Design:** Preserve propose_content's public signature and ContentProposals result. Validate inputs, then make at most two sequential calls: background-only facts and story-only quiz. Each branch has a dedicated prompt, a schema with the other array forced empty, and source aliases limited to that branch. Validate those restrictions again in Python. Missing branches require no call; empty output is valid abstention. Failures propagate to the existing bounded coordinator; no automatic retry or publication.

**Constraints:** Fixed local Ollama endpoint, no tools, verified model artifacts in CLI, existing overall deadline, at most eight batches. Eight mixed-evidence batches now permit sixteen generator calls plus eight baseline critic calls (or sixteen structured critic calls). No parallel GPU inference. Preserve prior combined prompt as a text artifact for historical reports.

## Tasks

- [x] Archive the current combined generator and implement branch-specific prompts/schema/code validation in content_proposal_learning.py.
- [x] Add tests showing evidence isolation, constrained aliases, forbidden cross-branch results, sequential calls, abstention and failure behavior. Keep critic tests.
- [x] Record generator policy/version in preparation reports; retain provenance, filtering, checkpointing and publication boundary.
- [x] Run backend checks and one bounded real Inception RAG/generation/review batch using the same first evidence batch as the previous run. Report observed behavior and cost without claiming benchmark improvement.
- [x] Write lesson 41 and update progress with exact results and limitations. Visible preparation/draft review remains the subsequent increment.

## Completion evidence

581 backend checks passed. One local same-evidence run: 43.66s, two facts/two story proposals passed source checks; two facts retained, both quiz proposals rejected by fallible critic. Exact trace and manual semantic observations preserved. No publication, frontend, or live-server changes.
