# AI Reliability Lab: showing evidence without overclaiming

PlotSpot already had many evaluation reports and pipeline traces, but they were scattered across JSON files, Markdown reports and private local databases. That made the engineering work difficult to demonstrate and easy to misinterpret. The AI Reliability Lab turns those existing records into one read-only development view while keeping the underlying evidence categories and privacy boundaries intact.

The lab does **not** run agents, change prompts, publish content or grade new outputs. It only explains evidence that already exists.

## What the user sees

The local `/lab` page has four parts:

1. **Quality at a glance** shows gated suites, held-out case counts and bounded recent-run status.
2. **Evidence by stage** maps search, facts, quiz and discuss onto retrieval, generation, verification and publication health.
3. **Measured evidence** lists each registered suite with its evidence category, metrics, sample size, source report and limitations.
4. **Recorded pipeline activity** shows safe stage summaries for recent content-preparation and Story RAG runs.

The UI says `7 / 12 cases` as well as `58.3%`. A percentage alone hides whether it came from twelve cases or twelve thousand. It also keeps development, held-out, smoke, live, publication and audit evidence separate because they answer different questions.

## End-to-end data flow

```text
registered report or bounded local run
                ↓
backend validator and explicit normalizer
                ↓
strict Pydantic response contract
                ↓ JSON
strict Zod validation in the browser
                ↓
React Query cache and PlotSpot UI
```

### 1. A fixed report registry

The backend owns the exact list of accepted evaluation files. The browser can ask for the overview, but it cannot provide a path. Before reading a registered file, the backend checks its canonical location, rejects symbolic links, enforces a size limit and then parses only the fields required by that report's normalizer.

This is safer than a generic `?path=...` endpoint. A path endpoint can accidentally become a local-file reader through `../`, symbolic links or a newly added sensitive file. A registry makes the trusted inputs reviewable in code.

### 2. Explicit normalization

Every artifact family has an explicit parser. The parser converts report-specific fields into a small common contract:

- suite identity, feature and evidence category;
- pass, attention, informational, unavailable or error status;
- bounded metrics with definitions;
- numerator and denominator for percentages;
- code-owned limitations and safe warnings.

Unknown report fields are not forwarded. Invalid or missing optional evidence becomes a warning. A malformed required gated report makes the overall state require attention instead of being silently skipped.

### 3. Safe run projection

Recent runs come from bounded local storage. SQLite is opened read-only, trace locations are fixed, and records are limited before projection. The API exposes movie identity, workflow, timestamps, counts, status and code-owned stage messages. It intentionally excludes prompts, retrieved passages, generated questions, answers, model output and chain-of-thought-like reasoning.

That distinction matters: observability needs enough information to diagnose *where* a workflow struggled without turning a developer screen into a raw-content or secret-exfiltration surface.

### 4. Two feature flags

The lab requires both flags during local development:

```dotenv
# backend/.env
PLOTSPOT_LAB_ENABLED=true

# frontend/.env.local
VITE_PLOTSPOT_LAB_ENABLED=true
```

The backend flag is the security boundary. When it is false, the API returns `404`, so a handcrafted request cannot use the lab. The frontend flag only makes `/lab` available in a Vite development build. The route is statically omitted from a production build.

## Why partial data is a valid state

Real observability systems rarely receive every signal at the same time. An optional report might be missing while two gated suites and recent runs remain valid. The lab returns the valid evidence, marks the overall state `partial`, and displays a warning explaining what is unavailable.

Failing the entire page would hide useful evidence. Pretending the missing report passed would be worse. Partial state preserves both usefulness and honesty.

## Gated versus informational evidence

A **gated** suite has a predefined pass decision and is allowed to affect readiness. An **informational** suite reports observations without pretending they are a release decision. For example, a small development agreement check can be useful for debugging but should not inflate a production-sounding pass rate.

This is why the lab reports `2 of 2 gated suites passing` instead of averaging every visible percentage. Arithmetic cannot make unlike datasets scientifically comparable.

## Caching and requests

React Query owns short-lived browser caching:

- the overview is reused briefly because registered reports change infrequently;
- the run list has a shorter stale period;
- run detail loads only after a row is opened;
- abort signals cancel obsolete requests when a filter changes or the page unmounts.

The API client uses only `GET` and requests `no-store` from HTTP caches. React Query's in-memory cache improves interaction without turning the browser or an intermediary into long-term storage for local operational metadata.

## Failure behavior

- Disabled lab: backend returns `404`; production frontend has no route.
- Missing optional report: valid evidence remains visible with a partial warning.
- Invalid required gated report: readiness requires attention.
- Missing run source: evaluation cards remain usable.
- Invalid API JSON: Zod rejects it instead of letting uncertain data reach components.
- Failed overview request: the page shows a retry action.
- No matching filter: the page explains that no evaluation matches.

## Concepts to explain afterwards

### Why is a registry safer than accepting a file path from the browser?

The registry limits reads to code-reviewed artifacts. The client cannot explore the filesystem, use path traversal or point at a secret. Canonical-path, symbolic-link and size checks add defence in depth.

### Why show `8 / 10` beside `80%`?

The fraction reveals sample size. `80%` from ten cases is much less certain than `80%` from ten thousand cases, so displaying only the percentage invites overconfidence.

### Why not merge development, held-out and live scores into one number?

They measure different conditions. Development cases may have influenced implementation, held-out cases estimate generalisation once, and live smoke checks verify a particular environment. Averaging them destroys that context.

### How does explicit projection prevent data leakage?

The backend constructs a new response from an allowlist of safe fields. It does not serialize database rows or report objects directly, so a future sensitive column or JSON key cannot appear automatically.

### Where do Pydantic and Zod each help?

Pydantic validates what the Python backend sends. Zod independently validates what the TypeScript frontend receives. Together they catch drift at the network boundary rather than allowing malformed data to fail deep in a component.

### Why can partial data still be correct?

Correctness includes representing uncertainty. If one optional source is missing, the other independently valid evidence does not become false. The honest result is valid data plus an explicit warning, not an empty page or a fabricated success.

### Is this an agent evaluation system or an application test dashboard?

It presents both, but does not confuse them. Deterministic tests establish software behavior such as schema validation and disabled routes. Registered evaluations measure selected model or pipeline behavior on labelled cases. Passing one does not prove the other.

## What remains before production observability

This local lab is a portfolio and development tool, not production monitoring. Production would still need authenticated operator access, centralized immutable telemetry, retention rules, redaction audits, distributed run identity, load and recovery benchmarks, alerting and independently labelled quality sets. Those are deliberately not implied by this dashboard.
