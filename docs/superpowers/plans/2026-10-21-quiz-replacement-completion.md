# Quiz Replacement Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible, proposal-only decision for all thirty-four saved-quiz replacement targets by recovering the thirty-one unresolved targets through explicit intent contracts, bounded evidence recovery and whole-bank novelty review.

**Architecture:** Add one focused completion-domain module for immutable target manifests and narrative intent contracts, then integrate its deterministic checks with the existing exact-answer-span writer. Extend the guarded movie-source corpus with a bounded targeted-story query, reuse the existing evidence reviewer and local Ollama writer in small checkpointed batches, and assemble one hash-pinned final report without exposing a publication path.

**Tech Stack:** Python 3.12, Pydantic v2, httpx, SQLite, pytest, local Ollama `qwen3.5:9b`, DuckDuckGo/Startpage discovery, existing PlotSpot public-web and content-store safeguards.

## Global Constraints

- This workflow is proposal-only: it must not update a saved quiz bank, publication receipt, runtime qualification or UI.
- Correct answers remain exact contiguous substrings of assistant-approved evidence.
- The thirty-four original `replace` decisions are the immutable scope; all must appear exactly once in the final report.
- Preserve the three already ready candidates unless their source report, candidate or saved-bank identity changes.
- Run local generation and review in batches of at most three targets.
- Use only the registered local `qwen3.5:9b` model and record its pinned digest.
- Search snippets are discovery metadata and can never become evidence.
- A newly fetched page must pass HTTPS, DNS, TLS, redirect, robots, size, identity, purpose and instruction-injection checks before storage.
- Allow at most eight ranked passages per target, two passages per source and two sources per publisher.
- One failed target cannot abort, weaken or erase decisions for sibling targets.
- Ambiguous novelty remains withheld; no override flag is permitted.
- The final publication audit must remain 20 banks, 20 receipts, 113 facts, 215 quiz items, 214 scored questions and 332 citations.

---

## File map

- Create `backend/src/movie_companion/quiz_replacement_completion.py`: strict manifest/contract models, lane derivation, intent checks and final report accounting.
- Create `backend/tests/test_quiz_replacement_completion.py`: unit coverage for immutable identities, lane counts, contracts, intent checks and complete accounting.
- Create `backend/scripts/prepare_quiz_replacement_manifest.py`: build the frozen thirty-one-target manifest from reviewed artifacts and the current content database.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json`: hash-pinned unresolved target manifest.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-intent-contracts-v1.json`: reviewed structured contracts for the thirty non-novelty targets.
- Modify `backend/src/movie_companion/quiz_replacement_span_writer.py`: release contracts to the local writer and apply deterministic contract checks after code copies the exact answer.
- Modify `backend/tests/test_quiz_replacement_span_writer.py`: prove contract prompting, intent rejection and sibling isolation.
- Modify `backend/src/movie_companion/movie_source_corpus.py`: add a bounded, cache-keyed targeted story query that retains all current source safeguards.
- Modify `backend/tests/test_multi_source_corpus.py`: prove targeted query identity, cache separation, fallback and publisher budgets.
- Modify `backend/src/movie_companion/quiz_replacement_evidence.py`: let the ranked local evidence query consume reviewed contract concepts.
- Modify `backend/tests/test_quiz_replacement_evidence.py`: prove contract-aware ranking remains complete-sentence and bounded.
- Create `backend/scripts/recover_quiz_replacement_evidence.py`: local-first, one-revised-query evidence recovery for seventeen targets.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-v1.json`: evidence recovery report.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-review-v1.json`: pinned local evidence-review decisions.
- Create `backend/scripts/prepare_quiz_replacement_completion.py`: checkpointed intent-aware generation and critic review for recovered targets.
- Create `backend/tests/test_prepare_quiz_replacement_completion.py`: runner identity, resume, retry and non-publication tests.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-candidates-v1.json`: local generation/critic results.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-editorial-v1.json`: assistant editorial decisions.
- Modify `backend/scripts/review_provisional_quiz_replacements.py`: add explicit novelty-adjudication context while retaining fail-closed decisions.
- Modify `backend/tests/test_provisional_quiz_replacements.py`: distinguish relationship change from name recall and verify uncertainty withholding.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-input-v1.json`: all editorial accepts plus the ambiguous candidate.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-review-v1.json`: whole-bank novelty decisions.
- Create `backend/scripts/assemble_quiz_replacement_completion.py`: validate hashes and assemble the final thirty-four-target proposal.
- Create `backend/tests/test_assemble_quiz_replacement_completion.py`: exact-scope, duplicate, stale-input and publication-boundary coverage.
- Create `evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json`: final ready/withheld proposal.
- Create `docs/learning/81-quiz-replacement-completion.md`: explain the three lanes, measured funnel and remaining limitations.
- Modify `docs/learning/PROGRESS.md` and `evals/README.md`: index the completed evaluation artifacts.

### Task 1: Freeze unresolved targets and reviewed intent contracts

**Files:**
- Create: `backend/src/movie_companion/quiz_replacement_completion.py`
- Create: `backend/tests/test_quiz_replacement_completion.py`
- Create: `backend/scripts/prepare_quiz_replacement_manifest.py`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-intent-contracts-v1.json`

**Interfaces:**
- Consumes: `build_targets(review: dict, bank: ContentStore) -> list[dict]` from `quiz_replacement_workflow.py`.
- Produces: `NarrativeIntent`, `CompletionTarget`, `CompletionManifest` Pydantic models.
- Produces: `build_completion_manifest(source_review: dict, evidence_review: dict, whole_bank_review: dict, bank: ContentStore) -> CompletionManifest`.
- Produces: `load_intent_contracts(path: Path, *, manifest: CompletionManifest) -> dict[str, NarrativeIntent]`.
- Produces artifact policy `quiz-replacement-completion-manifest-v1` with lane counts `13 intent`, `17 evidence`, `1 novelty`.

- [x] **Step 1: Write failing manifest and contract tests**

```python
import pytest

from movie_companion.quiz_replacement_completion import (
    CompletionManifest,
    NarrativeIntent,
    intent_contract_problems,
)

HASH = "0" * 64


def target(lane, index):
    return {
        "movie_id": index + 1,
        "title": f"Film {index}",
        "question_id": f"q{index}",
        "old_question": "What granular fact was tested?",
        "old_answer": "A granular answer",
        "replacement_brief": "Replace it with a meaningful narrative question.",
        "bank_version": f"research-{index}",
        "bank_sha256": HASH,
        "lane": lane,
        "originating_artifacts": {"review": HASH},
    }


def test_narrative_intent_accepts_reviewed_values_and_rejects_unknown_types():
    intent = NarrativeIntent(
        question_id="q1",
        focus="the choice to leave home",
        relation="motivation",
        required_concepts=[["protect", "save"], ["family"]],
        forbidden_details=["three years"],
        expected_answer_shape="reason",
        difficulty="general_viewer",
    )
    assert intent.expected_answer_shape == "reason"
    with pytest.raises(ValueError):
        NarrativeIntent(
            question_id="q1", focus="x", relation="technical_detail",
            required_concepts=[["x"]], forbidden_details=[],
            expected_answer_shape="number", difficulty="general_viewer",
        )


def test_manifest_requires_exact_lane_counts_and_unique_target_identity():
    rows = [target("intent", index) for index in range(13)]
    rows += [target("evidence", index) for index in range(13, 30)]
    rows += [target("novelty", 30)]
    manifest = CompletionManifest(
        policy="quiz-replacement-completion-manifest-v1",
        source_review_sha256=HASH,
        evidence_review_sha256=HASH,
        whole_bank_review_sha256=HASH,
        items=rows,
    )
    assert manifest.summary == {"unresolved": 31, "intent": 13, "evidence": 17, "novelty": 1}
    with pytest.raises(ValueError, match="Duplicate"):
        CompletionManifest(
            policy=manifest.policy,
            source_review_sha256=HASH,
            evidence_review_sha256=HASH,
            whole_bank_review_sha256=HASH,
            items=[rows[0], rows[0], *rows[2:]],
        )
```

- [x] **Step 2: Run the focused test and verify the missing-module failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_quiz_replacement_completion.py -q`

Expected: FAIL because `movie_companion.quiz_replacement_completion` does not exist.

- [x] **Step 3: Implement strict models and lane derivation**

```python
from collections import Counter
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from .content_proposals import StrictRecord
from .quiz_replacement_workflow import build_targets

POLICY = "quiz-replacement-completion-manifest-v1"
Lane = Literal["intent", "evidence", "novelty"]
Relation = Literal["motivation", "consequence", "relationship", "role", "choice", "theme", "ending", "story_rule"]
AnswerShape = Literal["reason", "outcome", "role", "relationship", "action", "state_change", "idea"]


class NarrativeIntent(StrictRecord):
    question_id: str = Field(min_length=1, max_length=200)
    focus: str = Field(min_length=3, max_length=240)
    relation: Relation
    required_concepts: list[list[str]] = Field(min_length=1, max_length=6)
    forbidden_details: list[str] = Field(default_factory=list, max_length=8)
    expected_answer_shape: AnswerShape
    difficulty: Literal["general_viewer"] = "general_viewer"

    @model_validator(mode="after")
    def bounded_aliases(self):
        if any(not 1 <= len(group) <= 5 for group in self.required_concepts):
            raise ValueError("Each required concept needs one to five aliases")
        if any(not all(isinstance(value, str) and 1 <= len(value.strip()) <= 80 for value in group)
               for group in self.required_concepts):
            raise ValueError("Invalid required concept alias")
        return self


class CompletionTarget(StrictRecord):
    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    question_id: str = Field(min_length=1, max_length=200)
    old_question: str = Field(min_length=1, max_length=250)
    old_answer: str = Field(min_length=1, max_length=150)
    replacement_brief: str = Field(min_length=10, max_length=500)
    bank_version: str = Field(min_length=1, max_length=120)
    bank_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lane: Lane
    originating_artifacts: dict[str, str]


class CompletionManifest(StrictRecord):
    policy: Literal[POLICY]
    source_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    whole_bank_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[CompletionTarget] = Field(min_length=31, max_length=31)

    @model_validator(mode="after")
    def exact_scope(self):
        ids = [(item.movie_id, item.question_id) for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate completion target")
        if Counter(item.lane for item in self.items) != Counter(intent=13, evidence=17, novelty=1):
            raise ValueError("Unexpected completion lane counts")
        return self

    @property
    def summary(self):
        counts = Counter(item.lane for item in self.items)
        return {"unresolved": len(self.items), **{key: counts[key] for key in ("intent", "evidence", "novelty")}}
```

Build lanes from reviewed state, never from title-specific hard-coding: three `ready_for_final_selection` rows are resolved; the sole editorial accept withheld by whole-bank novelty becomes `novelty`; accepted evidence without a ready/ambiguous candidate becomes `intent`; rejected evidence becomes `evidence`. Hash each current saved quiz with the canonical JSON helper already used by `review_provisional_quiz_replacements.py`.

- [x] **Step 4: Add contract loading and target consistency checks**

```python
def load_intent_contracts(path: Path, *, manifest: CompletionManifest):
    payload = json.loads(path.read_text())
    if payload.get("policy") != "quiz-replacement-intent-contracts-v1" or payload.get("status") != "reviewed":
        raise ValueError("Expected reviewed quiz replacement intent contracts")
    contracts = [NarrativeIntent.model_validate(item) for item in payload.get("items", [])]
    expected = {item.question_id for item in manifest.items if item.lane in ("intent", "evidence")}
    if {item.question_id for item in contracts} != expected or len(contracts) != len(expected):
        raise ValueError("Intent contracts do not match the generative target scope")
    return {item.question_id: item for item in contracts}
```

Create `replacement-intent-contracts-v1.json` with one reviewed contract for each of the thirty `intent` and `evidence` lane targets. Use concise aliases grounded in the replacement brief; forbidden details must be literal strings such as a count, duration or name that the brief explicitly excludes.

- [x] **Step 5: Generate and verify the frozen manifest**

Run:

```bash
cd backend
.venv/bin/python scripts/prepare_quiz_replacement_manifest.py \
  --source-review ../evals/movie-rag/quiz-narrative-quality/assistant-bank-review-v1.json \
  --evidence-review ../evals/movie-rag/quiz-narrative-quality/replacement-evidence-editorial-v1.json \
  --whole-bank-review ../evals/movie-rag/quiz-narrative-quality/provisional-whole-bank-review-v1.json \
  --database ../data/movie-content.db \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json
.venv/bin/python -m pytest tests/test_quiz_replacement_completion.py -q
```

Expected: the manifest reports exactly 31 unresolved targets across `13/17/1`, and all focused tests pass.

- [x] **Step 6: Commit the frozen completion scope**

```bash
git add backend/src/movie_companion/quiz_replacement_completion.py \
  backend/tests/test_quiz_replacement_completion.py \
  backend/scripts/prepare_quiz_replacement_manifest.py \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json \
  evals/movie-rag/quiz-narrative-quality/replacement-intent-contracts-v1.json
git commit -m "eval: freeze quiz replacement completion scope"
```

### Task 2: Enforce narrative intent around exact-answer generation

**Files:**
- Modify: `backend/src/movie_companion/quiz_replacement_completion.py`
- Modify: `backend/src/movie_companion/quiz_replacement_span_writer.py`
- Modify: `backend/tests/test_quiz_replacement_completion.py`
- Modify: `backend/tests/test_quiz_replacement_span_writer.py`

**Interfaces:**
- Consumes: `NarrativeIntent` and reviewed contract dictionary from Task 1.
- Produces: `intent_contract_problems(question: str, answer: str, *, intent: NarrativeIntent) -> list[str]`.
- Changes: `generate_locked_drafts(client, targets, *, model=MODEL)` expects each target to contain serialized `intent`.
- Preserves: code-owned exact answer copying and the existing `ReplacementDrafts` return type.

- [x] **Step 1: Write failing deterministic intent tests**

```python
def test_intent_contract_requires_every_concept_group_and_blocks_forbidden_details():
    intent = NarrativeIntent(
        question_id="q1", focus="Simba's return", relation="motivation",
        required_concepts=[["protect", "save"], ["kingdom", "Pride Lands"]],
        forbidden_details=["three years"], expected_answer_shape="reason",
    )
    assert intent_contract_problems(
        "Why does Simba return to the Pride Lands?", "To protect his kingdom", intent=intent
    ) == []
    assert "missing_required_concept" in intent_contract_problems(
        "Why does Simba return?", "Because he remembers home", intent=intent
    )
    assert "forbidden_detail" in intent_contract_problems(
        "Why does Simba return after three years?", "To protect his kingdom", intent=intent
    )


def test_expected_answer_shape_rejects_a_reason_answered_by_an_identity():
    intent = NarrativeIntent(
        question_id="q2", focus="the reason for the meeting", relation="motivation",
        required_concepts=[["control"]], forbidden_details=[], expected_answer_shape="reason",
    )
    assert "answer_shape_mismatch" in intent_contract_problems(
        "Who starts the meeting?", "Tyler Durden", intent=intent
    )
```

- [x] **Step 2: Run the focused tests and verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_quiz_replacement_completion.py tests/test_quiz_replacement_span_writer.py -q`

Expected: FAIL because `intent_contract_problems` and writer contract handling are absent.

- [x] **Step 3: Implement normalized concept and question-shape checks**

```python
SHAPE_PATTERNS = {
    "reason": (r"^why\b", r"\bwhat (?:reason|motivates?)\b"),
    "outcome": (r"\bwhat (?:happens|results|consequence)\b", r"\bhow does .+ affect\b"),
    "role": (r"\bwhat role\b", r"\bhow does .+ help\b", r"\bwhy is .+ important\b"),
    "relationship": (r"\brelationship\b", r"\bwhat changes between\b"),
    "action": (r"^what does\b", r"\bwhich (?:choice|action)\b", r"^how does\b"),
    "state_change": (r"\bhow does .+ change\b", r"\bwhat changes\b", r"\bwhat becomes\b"),
    "idea": (r"\bwhat idea\b", r"\bwhich theme\b", r"\bwhat does .+ (?:show|suggest|represent)\b"),
}


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def intent_contract_problems(question: str, answer: str, *, intent: NarrativeIntent):
    combined = _normal(f"{question} {answer}")
    problems = []
    if any(not any(_normal(alias) in combined for alias in group) for group in intent.required_concepts):
        problems.append("missing_required_concept")
    if any(_normal(detail) in combined for detail in intent.forbidden_details):
        problems.append("forbidden_detail")
    if not any(re.search(pattern, question.casefold()) for pattern in SHAPE_PATTERNS[intent.expected_answer_shape]):
        problems.append("answer_shape_mismatch")
    return problems
```

Keep this deliberately conservative. It recognizes reviewed aliases and ordinary question forms; it does not infer themes or movie facts.

- [x] **Step 4: Release the contract to the writer and run code-owned checks**

Add serialized `intent` to each writer record, update the prompt to state that every required-concept group needs one alias and no forbidden detail may appear, then apply the deterministic check after the selected exact answer is copied:

```python
intent = NarrativeIntent.model_validate(target["intent"])
problems = intent_contract_problems(item.question, selected["text"], intent=intent)
if problems:
    continue
```

Return target-level rejection reasons alongside drafts rather than silently losing the reason. Change the second return value to:

```python
LockedGeneration = dict[str, dict[str, object]]
# {"T1": {"answer_spans": [...], "writer_problems": [...]}}
```

Update `prepare_locked_span_quiz_replacements.py` and its tests to read `answer_spans` from this record while preserving its previous shaped-span output.

- [x] **Step 5: Run writer, workflow and intent suites**

Run:

```bash
cd backend
.venv/bin/python -m pytest \
  tests/test_quiz_replacement_completion.py \
  tests/test_quiz_replacement_span_writer.py \
  tests/test_quiz_replacement_workflow.py -q
```

Expected: PASS, including exact answer copying, cross-target isolation and explicit `intent_contract_not_satisfied` reasons.

- [x] **Step 6: Commit intent-constrained generation**

```bash
git add backend/src/movie_companion/quiz_replacement_completion.py \
  backend/src/movie_companion/quiz_replacement_span_writer.py \
  backend/scripts/prepare_locked_span_quiz_replacements.py \
  backend/tests/test_quiz_replacement_completion.py \
  backend/tests/test_quiz_replacement_span_writer.py
git commit -m "feat: constrain quiz replacements by narrative intent"
```

### Task 3: Add bounded targeted story-source recovery

**Files:**
- Modify: `backend/src/movie_companion/movie_source_corpus.py`
- Modify: `backend/tests/test_multi_source_corpus.py`
- Modify: `backend/src/movie_companion/quiz_replacement_evidence.py`
- Modify: `backend/tests/test_quiz_replacement_evidence.py`
- Create: `backend/scripts/recover_quiz_replacement_evidence.py`
- Create: `backend/tests/test_recover_quiz_replacement_evidence.py`

**Interfaces:**
- Consumes: `MovieIdentity`, `MovieSourceCorpus`, `WebCorpusStore`, `CompletionManifest`, and reviewed contracts.
- Produces: `targeted_story_query(movie: MovieIdentity, intent: NarrativeIntent, *, revision: int) -> str`.
- Produces: `MovieSourceCorpus.targeted_story(movie, query, *, refresh=False) -> CorpusResult`.
- Changes: `retrieve_replacement_evidence(store, target, *, intent=None, limit=8)` adds reviewed concept aliases to BM25 terms.
- Produces artifact policy `quiz-replacement-evidence-recovery-v1`.

- [x] **Step 1: Write failing targeted-query and recovery tests**

```python
from movie_companion.quiz_replacement_completion import NarrativeIntent


def reviewed_intent():
    return NarrativeIntent(
        question_id="q1", focus="the consequence for the family",
        relation="consequence", required_concepts=[["family"], ["protect", "save"]],
        forbidden_details=[], expected_answer_shape="outcome",
    )


def test_targeted_story_query_contains_movie_identity_and_reviewed_concepts_only():
    query = targeted_story_query(MOVIE, reviewed_intent(), revision=1)
    assert query.startswith('"Interstellar" 2014 film')
    assert "consequence" in query and "family" in query
    assert len(query) <= 500
    with pytest.raises(ValueError):
        targeted_story_query(MOVIE, reviewed_intent(), revision=3)


def test_targeted_story_has_a_distinct_cache_key_and_keeps_five_page_budget(tmp_path):
    class Search:
        provider = "duckduckgo"
        def __init__(self): self.queries = []
        async def search(self, query, limit):
            self.queries.append(query)
            return [SearchHit("Interstellar", f"https://publisher{i}.example/story", "discovery", i + 1)
                    for i in range(5)]
    class Reader:
        async def fetch(self, url):
            return WebRead(url, article(), "text/html")
    search = Search()
    corpus = MovieSourceCorpus(search, Reader(), WebCorpusStore(tmp_path / "corpus.db"))
    async def run():
        first = await corpus.targeted_story(MOVIE, '"Interstellar" 2014 film family consequence')
        second = await corpus.targeted_story(MOVIE, '"Interstellar" 2014 film ending choice')
        await corpus.close()
        return first, second
    first, second = asyncio.run(run())
    assert search.queries == ['"Interstellar" 2014 film family consequence',
                              '"Interstellar" 2014 film ending choice']
    assert len(first.sources) <= 5 and len(second.sources) <= 5


def test_contract_terms_improve_ranking_without_releasing_partial_sentences(tmp_path):
    store = WebCorpusStore(tmp_path / "ranked.db")
    store.remember(source(), "web")
    target = {
        "movie_id": 1,
        "old_question": "Where do they go after the flood?",
        "replacement_brief": "Replace with the consequence of the flood for the family.",
        "evidence": {"explanation": "The flood displaces the family."},
    }
    evidence, trace = retrieve_replacement_evidence(
        store, target, intent=reviewed_intent(), limit=8
    )
    assert evidence[0]["excerpt"].endswith(".")
    assert any(alias in trace["query_terms"] for alias in ("family", "protect"))
    assert len(evidence) <= 8
```

- [x] **Step 2: Run tests and verify the missing-interface failures**

Run: `cd backend && .venv/bin/python -m pytest tests/test_multi_source_corpus.py tests/test_quiz_replacement_evidence.py tests/test_recover_quiz_replacement_evidence.py -q`

Expected: FAIL because targeted-story acquisition and contract-aware retrieval are absent.

- [x] **Step 3: Add query-keyed acquisition without weakening source policy**

Refactor only the discovery query input; keep `_web` acquisition, `make_web_source`, publisher caps, full-page identity checks and `WebCorpusStore.remember` unchanged:

```python
def targeted_key(self, movie, query):
    return hashlib.sha256(
        f"{POLICY}:targeted-story:{movie.fingerprint}:{self.search.provider}:{query}".encode()
    ).hexdigest()


async def targeted_story(self, movie, query, *, refresh=False):
    if not isinstance(query, str) or not 1 <= len(query) <= 500:
        raise ValueError("Targeted story query exceeds budget")
    key = self.targeted_key(movie, query)
    return await self._web_for_query(movie, "story", key, query, refresh=refresh)
```

The shared helper calls `self.search.search(query, limit=15)`, accepts at most five validated pages, keeps two pages per publisher, uses stale cache on provider failure, and stores the query hash rather than raw query text in cache metadata.

- [x] **Step 4: Add bounded query construction and contract-aware BM25**

```python
def targeted_story_query(movie, intent, *, revision):
    if revision not in (1, 2):
        raise ValueError("Only an initial and one revised query are allowed")
    concepts = [group[min(revision - 1, len(group) - 1)] for group in intent.required_concepts]
    title = re.sub(r"[^\w .,:!?()-]", " ", movie.title)[:160]
    query = " ".join((f'"{title}"', str(movie.year or ""), "film", intent.relation,
                      intent.focus, *concepts))
    query = " ".join(query.split())
    if len(query) > 500:
        raise ValueError("Targeted story query exceeds budget")
    return query
```

In `retrieve_replacement_evidence`, add each reviewed alias group to the lexical query when `intent` is present, but keep the existing complete-sentence extractor, 8,000-candidate ceiling, per-source cap and per-publisher cap.

- [x] **Step 5: Implement the local-first recovery script**

For each of the seventeen `evidence` targets:

1. rerun contract-aware retrieval over the existing corpus;
2. if fewer than two useful passages are ranked, acquire the initial targeted story query;
3. rerun retrieval;
4. if evidence review later returns `insufficient`, allow one explicit `--revision 2` run into a new output path;
5. record source errors per target and continue.

The script must reject `--revision` outside `1..2`, an output file that already contains a different manifest/contract hash, or any manifest whose lane counts differ from `13/17/1`.

- [x] **Step 6: Run focused source and recovery tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest \
  tests/test_multi_source_corpus.py \
  tests/test_quiz_replacement_evidence.py \
  tests/test_quiz_replacement_evidence_review.py \
  tests/test_recover_quiz_replacement_evidence.py -q
```

Expected: PASS with no search snippet present in returned evidence.

- [x] **Step 7: Commit bounded evidence recovery**

```bash
git add backend/src/movie_companion/movie_source_corpus.py \
  backend/src/movie_companion/quiz_replacement_evidence.py \
  backend/scripts/recover_quiz_replacement_evidence.py \
  backend/tests/test_multi_source_corpus.py \
  backend/tests/test_quiz_replacement_evidence.py \
  backend/tests/test_recover_quiz_replacement_evidence.py
git commit -m "feat: recover targeted quiz story evidence"
```

### Task 4: Run checkpointed completion generation

**Files:**
- Create: `backend/scripts/prepare_quiz_replacement_completion.py`
- Create: `backend/tests/test_prepare_quiz_replacement_completion.py`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-v1.json`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-review-v1.json`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-candidates-v1.json`

**Interfaces:**
- Consumes: manifest and contracts from Task 1, original accepted evidence, recovered evidence review, `generate_locked_drafts`, and `review_drafts`.
- Produces: `run(args) -> None` with atomic checkpoint policy `quiz-replacement-completion-candidates-v1`.
- Produces: `resume_rows(path: Path, identity: dict) -> list[dict]`, `run_batch(client, targets: list[dict]) -> list[dict]`, and `build_report(identity: dict, rows: list[dict]) -> dict` for isolated tests.
- Produces per-target reasons `no_natural_exact_answer_span`, `intent_contract_not_satisfied`, `writer_abstained`, deterministic problems and critic decisions.

- [x] **Step 1: Write failing checkpoint and publication-boundary tests**

```python
from movie_companion.local_models import DIGESTS
from movie_companion.quiz_replacement_workflow import ReplacementDraft, ReplacementDrafts


def valid_identity(*, planned):
    return {
        "policy": POLICY, "manifest_sha256": "2" * 64,
        "contracts_sha256": "1" * 64, "source_review_sha256": "3" * 64,
        "evidence_review_sha256": "4" * 64, "model": "qwen3.5:9b",
        "model_digest": DIGESTS["qwen3.5:9b"], "planned": planned,
    }


def completion_target(question_id):
    return {
        "movie_id": 1, "title": "Film", "question_id": question_id,
        "old_question": "What old fact was tested?",
        "replacement_brief": "Test why the choice protects the family.",
        "remaining_questions": [],
        "evidence": {"citations": [{"source_label": "Source", "source_ref": "https://example.com/story",
                                      "revision": "r1", "excerpt": "The choice protects the family."}]},
        "intent": {"question_id": question_id, "focus": "the choice", "relation": "motivation",
                   "required_concepts": [["protects"], ["family"]], "forbidden_details": [],
                   "expected_answer_shape": "reason", "difficulty": "general_viewer"},
    }


def span(identifier):
    return {"span_id": identifier, "citation_index": 0,
            "text": "protects the family", "score": 10.0}


def one_valid_replacement_draft(target_id):
    return ReplacementDrafts(items=[ReplacementDraft(
        target_id=target_id, question="Why does the character make the choice?",
        options=["protects the family", "wins a prize", "finds a map", "changes a name"],
        correct_index=0, evidence_quote="The choice protects the family.",
    )])


async def one_accepted_review(client, *, targets, drafts):
    return [{"target_id": "T1", "candidate": drafts.items[0].model_dump(),
             "deterministic_problems": [], "critic": {"decision": "accept"},
             "ready_for_assistant_review": True}]


def withheld_row(question_id):
    return {"movie_id": 1, "question_id": question_id, "candidate": None,
            "withheld_reason": "writer_abstained", "ready_for_assistant_review": False}


def test_completion_runner_rejects_stale_checkpoint(tmp_path):
    output = tmp_path / "checkpoint.json"
    identity = valid_identity(planned=30)
    output.write_text(json.dumps({
        "status": "running", "policy": POLICY,
        "manifest_sha256": "0" * 64, "contracts_sha256": "1" * 64,
        "source_review_sha256": "3" * 64, "evidence_review_sha256": "4" * 64,
        "model": "qwen3.5:9b", "model_digest": DIGESTS["qwen3.5:9b"],
        "planned": 30, "items": [], "published": False,
    }))
    with pytest.raises(ValueError, match="checkpoint identity"):
        MODULE.resume_rows(output, identity)


def test_target_failure_does_not_drop_successful_sibling(monkeypatch, tmp_path):
    async def fake_generate(client, targets):
        return one_valid_replacement_draft("T1"), {
            "T1": {"answer_spans": [span("S1")], "writer_problems": []},
            "T2": {"answer_spans": [span("S1")],
                   "writer_problems": ["intent_contract_not_satisfied"]},
        }
    monkeypatch.setattr(MODULE, "generate_locked_drafts", fake_generate)
    monkeypatch.setattr(MODULE, "review_drafts", one_accepted_review)
    rows = asyncio.run(MODULE.run_batch(None, [completion_target("q1"), completion_target("q2")]))
    report = MODULE.build_report(valid_identity(planned=2), rows)
    assert {item["question_id"] for item in report["items"]} == {"q1", "q2"}
    assert report["items"][1]["withheld_reason"] == "intent_contract_not_satisfied"


def test_completion_runner_never_opens_a_publication_transaction(monkeypatch, tmp_path):
    monkeypatch.setattr(ContentStore, "publish", lambda *a, **k: pytest.fail("publication forbidden"))
    report = MODULE.build_report(valid_identity(planned=1), [withheld_row("q1")])
    assert report["publication"] == {"authorized": False, "database_mutated": False}
```

- [x] **Step 2: Run the runner tests and verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prepare_quiz_replacement_completion.py -q`

Expected: FAIL because the completion runner does not exist.

- [x] **Step 3: Implement immutable resume identity and per-target rows**

```python
CHECKPOINT_KEYS = (
    "policy", "manifest_sha256", "contracts_sha256",
    "source_review_sha256", "evidence_review_sha256",
    "model", "model_digest", "planned",
)


def resume_rows(path, identity):
    if not path.is_file():
        return []
    checkpoint = json.loads(path.read_text())
    if checkpoint.get("status") != "running" or any(
        checkpoint.get(key) != value for key, value in identity.items()
    ):
        raise ValueError("Completion checkpoint identity changed")
    ids = [item["question_id"] for item in checkpoint.get("items", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate completion checkpoint target")
    return checkpoint["items"]
```

Assemble generation work from the thirteen `intent` targets plus any `evidence` target whose recovered evidence status is `supported`. Add reviewed `intent` and citation records to each target, preflight `answer_spans`, then process batches of at most three. Catch only target-scoped model/schema/http failures, record their type and continue; allow `CancelledError` to propagate.

- [x] **Step 4: Retrieve and review the seventeen evidence gaps**

Run the first bounded recovery pass:

```bash
cd backend
.venv/bin/python scripts/recover_quiz_replacement_evidence.py \
  --manifest ../evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json \
  --contracts ../evals/movie-rag/quiz-narrative-quality/replacement-intent-contracts-v1.json \
  --catalog ../data/private/movie-catalog.db \
  --corpus data/private/web-corpus.db \
  --revision 1 \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-v1.json
.venv/bin/python scripts/review_quiz_replacement_evidence.py \
  --input ../evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-v1.json \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-review-v1.json
```

For evidence-review `insufficient` rows, run revision 2 once into `replacement-recovery-evidence-v2.json`, review it into `replacement-recovery-evidence-review-v2.json`, and merge only newly supported, hash-pinned decisions. Never overwrite the first-pass reports.

- [x] **Step 5: Run intent-aware generation**

```bash
cd backend
.venv/bin/python scripts/prepare_quiz_replacement_completion.py \
  --manifest ../evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json \
  --contracts ../evals/movie-rag/quiz-narrative-quality/replacement-intent-contracts-v1.json \
  --source-review ../evals/movie-rag/quiz-narrative-quality/assistant-bank-review-v1.json \
  --original-evidence-review ../evals/movie-rag/quiz-narrative-quality/replacement-evidence-editorial-v1.json \
  --recovered-evidence-review ../evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-review-v1.json \
  --database ../data/movie-content.db \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-completion-candidates-v1.json
```

Expected: every eligible target has one candidate or one explicit withheld reason; report fields remain `status=proposal_only`, `published=false`, and `database_mutated=false`.

- [x] **Step 6: Run focused runner tests and commit**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prepare_quiz_replacement_completion.py tests/test_quiz_replacement_span_writer.py tests/test_quiz_replacement_workflow.py -q`

Expected: PASS.

```bash
git add backend/scripts/prepare_quiz_replacement_completion.py \
  backend/tests/test_prepare_quiz_replacement_completion.py \
  evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-v1.json \
  evals/movie-rag/quiz-narrative-quality/replacement-recovery-evidence-review-v1.json \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-candidates-v1.json
git commit -m "eval: generate intent-bound quiz replacements"
```

### Task 5: Perform editorial and independent whole-bank review

**Files:**
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-editorial-v1.json`
- Modify: `backend/scripts/review_provisional_quiz_replacements.py`
- Modify: `backend/tests/test_provisional_quiz_replacements.py`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-input-v1.json`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-review-v1.json`

**Interfaces:**
- Consumes: completion candidates, their intent contracts and the existing ambiguous *Forrest Gump* candidate.
- Changes: each whole-bank input item may include `adjudication_context` with `candidate_intent`, `compared_bank_intent`, and `decision_rule`.
- Produces: `validate_selection(selection: dict) -> dict` and `ready_from_reviews(reviews: list[NoveltyReview], error_type: str | None) -> bool`.
- Preserves: `review_quiz_novelty(...)` remains the decision engine; only `new + clear` becomes ready.

- [x] **Step 1: Write failing adjudication-context tests**

```python
from types import SimpleNamespace


def test_adjudication_context_is_released_as_data_not_prompt_authority():
    packet = {
        "source_report": "evals/movie-rag/quiz-narrative-quality/replacement-shaped-span-editorial-v1.json",
        "source_report_sha256": "0" * 64,
        "movie_id": 13,
        "question_id": "q-forrest",
        "candidate_sha256": "1" * 64,
        "adjudication_context": {
            "candidate_intent": "how Forrest's relationship changes when he becomes a father",
            "compared_bank_intent": "recall the name of Jenny's son",
            "decision_rule": "same viewer knowledge means duplicate",
        },
    }
    normalized = MODULE.validate_selection(packet)
    assert normalized["adjudication_context"]["decision_rule"] == "same viewer knowledge means duplicate"


def test_uncertain_novelty_is_always_withheld():
    uncertain = SimpleNamespace(novelty="uncertain", clarity="clear")
    duplicate = SimpleNamespace(novelty="duplicate", clarity="clear")
    unclear = SimpleNamespace(novelty="new", clarity="needs_edit")
    ready = SimpleNamespace(novelty="new", clarity="clear")
    assert MODULE.ready_from_reviews([uncertain], None) is False
    assert MODULE.ready_from_reviews([duplicate], None) is False
    assert MODULE.ready_from_reviews([unclear], None) is False
    assert MODULE.ready_from_reviews([ready], "TimeoutError") is False
    assert MODULE.ready_from_reviews([ready], None) is True
```

- [x] **Step 2: Run provisional review tests and verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provisional_quiz_replacements.py -q`

Expected: FAIL because contextual adjudication is not yet accepted by the packet schema.

- [x] **Step 3: Add bounded independent adjudication context**

Validate each optional context field as non-empty text of at most 300 characters. Append it to the novelty review input as untrusted comparison data; do not tell the model which verdict to choose. Keep the rule explicit:

```python
ADJUDICATION_RULE = (
    "Treat the candidate as duplicate only when answering it demonstrates "
    "essentially the same viewer knowledge as the compared bank question."
)
```

Hash the full input packet, preserve the bank hash before and after each review, and continue withholding `duplicate`, `uncertain`, `needs_edit` or any error.

- [x] **Step 4: Create the assistant editorial report**

Review every critic-approved candidate against:

- exact evidence and correct answer;
- all required contract concepts;
- forbidden details;
- natural answer type and distractors;
- meaningful general-viewer story understanding; and
- remaining saved questions for the movie.

Write one row per completion target with `final_review` equal to `editorial_accept`, `editorial_reject` or `pipeline_withheld`, plus a concrete `reason`. Validate the report against the candidate-report hash before it becomes whole-bank input.

- [x] **Step 5: Run whole-bank review for all editorial accepts and the ambiguous candidate**

```bash
cd backend
.venv/bin/python scripts/review_provisional_quiz_replacements.py \
  --input ../evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-input-v1.json \
  --database ../data/movie-content.db \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-review-v1.json
```

Expected: every input receives a recorded novelty and clarity result or a target-level error; only `new + clear` rows are ready.

- [x] **Step 6: Run tests and commit review artifacts**

Run: `cd backend && .venv/bin/python -m pytest tests/test_provisional_quiz_replacements.py tests/test_quiz_novelty.py -q`

Expected: PASS.

```bash
git add backend/scripts/review_provisional_quiz_replacements.py \
  backend/tests/test_provisional_quiz_replacements.py \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-editorial-v1.json \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-input-v1.json \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-review-v1.json
git commit -m "eval: review completed quiz replacements"
```

### Task 6: Assemble the complete thirty-four-target proposal

**Files:**
- Create: `backend/scripts/assemble_quiz_replacement_completion.py`
- Create: `backend/tests/test_assemble_quiz_replacement_completion.py`
- Create: `evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json`

**Interfaces:**
- Consumes: original 34-target review, manifest, existing three ready rows, completion editorial report and completion whole-bank review.
- Produces: `assemble(inputs: CompletionInputs, bank: ContentStore) -> dict`.
- Produces: `exact_scope(original: dict, decisions: list[dict]) -> None`, `verify_hash(label: str, value: object, expected: str) -> None`, and `build_final_report(decisions: list[dict], input_hashes: dict[str, str]) -> dict`.
- Produces final policy `quiz-replacement-completion-final-v1` with exactly thirty-four decisions.

- [x] **Step 1: Write failing complete-accounting tests**

```python
def original_review():
    return {"decisions": [
        {"movie_id": index + 1, "question_id": f"q{index}", "disposition": "replace"}
        for index in range(34)
    ]}


def decisions():
    return [
        {"movie_id": index + 1, "question_id": f"q{index}",
         "decision": "ready" if index < 3 else "withheld",
         "withheld_reason": None if index < 3 else "quality_gate_not_passed"}
        for index in range(34)
    ]


def test_final_report_accounts_for_every_original_replacement_once():
    rows = decisions()
    MODULE.exact_scope(original_review(), rows)
    report = MODULE.build_final_report(rows, {"manifest": "0" * 64})
    identities = [(row["movie_id"], row["question_id"]) for row in report["items"]]
    assert len(identities) == len(set(identities)) == 34
    assert report["summary"]["ready"] + report["summary"]["withheld"] == 34
    assert all(row["decision"] in ("ready", "withheld") for row in report["items"])


def test_stale_candidate_or_bank_hash_is_rejected():
    with pytest.raises(ValueError, match="changed"):
        MODULE.verify_hash("candidate changed", {"question": "changed"}, "0" * 64)


def test_final_report_has_no_publication_authority():
    report = MODULE.build_final_report(decisions(), {"manifest": "0" * 64})
    assert report["status"] == "proposal_only"
    assert report["published"] is False
    assert report["publication"] == {"authorized": False, "database_mutated": False}
```

- [x] **Step 2: Run assembler tests and verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_assemble_quiz_replacement_completion.py -q`

Expected: FAIL because the assembler does not exist.

- [x] **Step 3: Implement hash-pinned exact-scope assembly**

```python
def exact_scope(original, decisions):
    expected = {
        (row["movie_id"], row["question_id"])
        for row in original["decisions"] if row["disposition"] == "replace"
    }
    actual = [(row["movie_id"], row["question_id"]) for row in decisions]
    if len(actual) != len(set(actual)) or set(actual) != expected or len(actual) != 34:
        raise ValueError("Final replacement decisions do not match original scope")


def final_decision(row):
    ready = bool(row.get("ready_for_final_selection"))
    return {
        **row,
        "decision": "ready" if ready else "withheld",
        "withheld_reason": None if ready else row.get("withheld_reason") or "quality_gate_not_passed",
    }


def verify_hash(label, value, expected):
    if canonical_sha256(value) != expected:
        raise ValueError(f"{label} changed")


def build_final_report(decisions, input_hashes):
    ready = sum(row["decision"] == "ready" for row in decisions)
    return {
        "policy": "quiz-replacement-completion-final-v1",
        "status": "proposal_only", "published": False,
        "input_hashes": input_hashes,
        "summary": {"targets": len(decisions), "ready": ready,
                    "withheld": len(decisions) - ready},
        "items": sorted(decisions, key=lambda row: (row["movie_id"], row["question_id"])),
        "publication": {"authorized": False, "database_mutated": False},
    }
```

Before adding a ready row, revalidate candidate hash, source report hash, current bank hash, grounding, intent checks, novelty `new`, wording `clear` and assistant editorial acceptance. Sort output by `(movie_id, question_id)` and include per-lane funnel counts, latency, retries, accepted/rejected new sources and grouped withheld reasons.

- [x] **Step 4: Generate and inspect the final proposal**

```bash
cd backend
.venv/bin/python scripts/assemble_quiz_replacement_completion.py \
  --source-review ../evals/movie-rag/quiz-narrative-quality/assistant-bank-review-v1.json \
  --manifest ../evals/movie-rag/quiz-narrative-quality/replacement-completion-manifest-v1.json \
  --existing-whole-bank ../evals/movie-rag/quiz-narrative-quality/provisional-whole-bank-review-v1.json \
  --completion-editorial ../evals/movie-rag/quiz-narrative-quality/replacement-completion-editorial-v1.json \
  --completion-whole-bank ../evals/movie-rag/quiz-narrative-quality/replacement-completion-whole-bank-review-v1.json \
  --database ../data/movie-content.db \
  --output ../evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json
```

Expected: summary totals equal 34; each withheld row contains a concrete reason; publication remains disabled.

- [x] **Step 5: Run assembler tests and commit**

Run: `cd backend && .venv/bin/python -m pytest tests/test_assemble_quiz_replacement_completion.py tests/test_quiz_replacement_completion.py -q`

Expected: PASS.

```bash
git add backend/scripts/assemble_quiz_replacement_completion.py \
  backend/tests/test_assemble_quiz_replacement_completion.py \
  evals/movie-rag/quiz-narrative-quality/replacement-completion-final-v1.json
git commit -m "eval: assemble complete quiz replacement proposal"
```

### Task 7: Document results and verify unchanged publication state

**Files:**
- Create: `docs/learning/81-quiz-replacement-completion.md`
- Modify: `docs/learning/PROGRESS.md`
- Modify: `evals/README.md`

**Interfaces:**
- Consumes: final completion report and publication audit.
- Produces: learner-facing explanation and reproducible artifact index.

- [x] **Step 1: Run all focused tests**

```bash
cd backend
.venv/bin/python -m pytest \
  tests/test_quiz_replacement_completion.py \
  tests/test_quiz_replacement_span_writer.py \
  tests/test_quiz_replacement_evidence.py \
  tests/test_quiz_replacement_evidence_review.py \
  tests/test_recover_quiz_replacement_evidence.py \
  tests/test_prepare_quiz_replacement_completion.py \
  tests/test_provisional_quiz_replacements.py \
  tests/test_assemble_quiz_replacement_completion.py -q
```

Expected: PASS.

- [x] **Step 2: Run the full backend suite and static checks**

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m py_compile \
  src/movie_companion/quiz_replacement_completion.py \
  src/movie_companion/quiz_replacement_span_writer.py \
  src/movie_companion/quiz_replacement_evidence.py \
  src/movie_companion/movie_source_corpus.py \
  scripts/prepare_quiz_replacement_manifest.py \
  scripts/recover_quiz_replacement_evidence.py \
  scripts/prepare_quiz_replacement_completion.py \
  scripts/review_provisional_quiz_replacements.py \
  scripts/assemble_quiz_replacement_completion.py
cd ..
git diff --check
```

Expected: all tests pass, `py_compile` is silent, and `git diff --check` reports no errors.

- [x] **Step 3: Run the publication audit and compare immutable totals**

Run the existing narrative audit command documented in `evals/README.md`, then verify:

```text
20 saved banks
20 publication receipts
113 facts
215 quiz items
214 scored questions
332 citations
```

Restore timestamp-only audit changes after confirming the totals so the branch contains no unrelated report churn.

- [x] **Step 4: Write the learning note and indexes**

Document:

- why the 31 unresolved targets needed three different recovery lanes;
- before/after funnel counts for each lane;
- examples of intent checks that prevented plausible but wrong questions;
- which new sources were accepted or rejected and why;
- the final ready/withheld split with grouped reasons;
- why a local critic is useful but does not replace editorial review; and
- why the completed proposal still does not publish content.

Add direct links to all manifest, contract, evidence, candidate, editorial, whole-bank and final artifacts in `evals/README.md` and record the outcome in `docs/learning/PROGRESS.md`.

- [x] **Step 5: Commit final verification and documentation**

```bash
git add docs/learning/81-quiz-replacement-completion.md \
  docs/learning/PROGRESS.md evals/README.md
git commit -m "docs: record quiz replacement completion results"
```

- [x] **Step 6: Push the feature branch and update the existing PR**

Run: `git push plotspot feature/plotspot-initial-import`

Expected: the existing PlotSpot pull request contains the complete proposal, tests and learning material; `main` remains unchanged.
