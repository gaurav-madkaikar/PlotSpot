# 71 — Movie RAG from multiple public sources

PlotSpot now has a configurable free web-search adapter alongside Wikipedia and available IMSDb scripts. It uses explicit Python orchestration, not LangChain: the responsibilities below apply regardless of framework.

## Source roles

- **Quiz:** released-film Wikipedia/story pages are answer evidence. Available screenplay scenes supplement the writer's context. Drafts cannot establish the correct option. A web-derived quiz answer additionally needs independent Wikipedia support before retention/publication.
- **Facts:** Wikipedia production sections, production articles and reviewed publisher snapshots. Scripts and plot-only sections are excluded. Facts still pass support, purpose and novelty checks, followed by the existing operator publication workflow.
- **Discuss:** the union of story/background web pages, Wikipedia, available script context, cached reviewed TIME/BFI articles and approved Caltech citation excerpts. Community comments, accounts and private history are not factual evidence.

The existing registered-film boundary remains: enabling search does not make all catalog movies automatically eligible for AI content. Expanding and independently qualifying that coverage is separate work.

## Follow the code

1. `movie_web_sources.MovieIdentity` builds public title/year/topic queries from TMDB metadata. A person's private discussion question is not sent to the search engine.
2. `web_search.FreeMovieSearch` runs DDGS in a bounded, killable child process. Its environment excludes application credentials. DuckDuckGo and Startpage are selectable exact backends; no paid key, proxy rotation or CAPTCHA bypass is used.
3. `public_web.PublicWebReader` follows only bounded public HTTPS reads. It checks DNS and redirects, pins the resolved address while retaining the original TLS hostname, respects robots rules on every destination, and rejects private addresses, credentials, unexpected content types and oversized bodies.
4. `movie_web_sources.make_web_source` extracts full visible paragraphs, checks movie identity and rejects obvious injected instructions. It separates story and production pools. Search-result snippets are candidate descriptions, never answer evidence.
5. `movie_source_corpus.MovieSourceCorpus` acquires up to five validated pages per purpose, rejects duplicates and limits pages per publisher. Search rank is candidate order, not credibility. An unavailable or thin search is recorded as degraded coverage.
6. `web_corpus_store.WebCorpusStore` stores immutable source text, sections, URLs, revisions, hashes and capture times in private SQLite. A shared movie/purpose bundle expires after 24 hours when complete or ten minutes when partial. A last-good bundle can survive a failed refresh for up to seven days after expiry. Existing snapshots created before the timestamp migration have unknown capture times.
7. `ingestion_learning.ingest_source` embeds source chunks with local `nomic-embed-text:v1.5` into the existing Chroma store. A source revision plus model/chunk settings identifies the embedding snapshot, so repeated requests reuse it.
8. `multi_source_pipeline.bounded_pool` ranks within each source when the combined corpus exceeds 400 passages, retains neighboring citation windows and then forms a bounded combined pool. The existing word/vector retriever and exact-quote/support reviewer answer the question. Unverified script-only answers abstain.
9. `research_workflow` spreads generation tasks across sources. Writers use bounded evidence, critics check support/purpose, and novelty checks compare against saved questions. `source_corroboration` independently checks web quiz answers against complete Wikipedia sentences. `research_checkpoint` verifies retained proof against the immutable reference text before accepting it.
10. The current preparation/publication workflow and compare-and-swap bank writes remain. Installing this feature does not regenerate or replace the eleven published banks. Additional quiz questions are saved only after the applicable checks pass.

## Configuration

In `backend/.env` choose `PLOTSPOT_MOVIE_WEB_SEARCH=duckduckgo`, `startpage`, or `off`. This integration is enabled in TMDB mode. The local configuration currently selects DuckDuckGo. The optional `PLOTSPOT_WEB_CORPUS_DB` selects a private corpus database location. Never commit credentials or private corpus data.

DDGS needs no API key for these backends, but this is not a contracted search API or an availability guarantee. Provider blocking, no results and extraction failures are normal operational possibilities. Startpage was unavailable in the live check; DuckDuckGo returned usable story pages but failed the production-trivia query. Reduced coverage must not be reported as five successfully verified sources.

## What the checks establish

The offline labelled dataset in `evals/movie-rag/multi-source/source-policy-cases-v1.json` contains authored inputs and accept/reject expectations. Its runner is `backend/scripts/evaluate_movie_sources.py`. It checks movie identity, thin pages, prompt injection, unsafe targets and story/production routing. It is not a live search relevance or LLM accuracy benchmark.

Run from the repository root:

```sh
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/evaluate_movie_sources.py --dataset evals/movie-rag/multi-source/source-policy-cases-v1.json --report .cache/source-policy-report.json
```

The live local-model proof and provider results are documented alongside that dataset. A correctly quoted blog claim can still be false: the initial draft check exposed misleading death/timing claims. Independent reference checking was added for web quiz answers. Model reviewers remain fallible, and these small development examples are now consumed; use fresh human-labelled cases before claiming production accuracy.

## Questions and answers

**Is collecting pages already RAG?** No. Collection supplies documents. RAG adds chunking, embedding, retrieval and evidence-grounded generation. Here SQLite retains source provenance and Chroma retains embeddings; they have different jobs.

**Why fetch full pages if search already returns text?** Snippets can be incomplete, outdated or about another movie. The system must examine the page and retain the exact text it later cites.

**Why separate story from production?** A good plot paragraph is inappropriate evidence for a behind-the-scenes fact. Purpose routing happens before writing, and reviewers check the generated content again.

**Does five sources mean an answer is true?** No. Pages can repeat one another or contain mistakes. Identity and duplication checks help, but answer support, independent references, source credibility and human-labelled evaluation are still needed.

**Why is a script not enough for a quiz answer?** It may be an early draft whose scenes differ from the released film. The writer may use its context, but the selected answer needs released-film evidence.

**What is cached?** Shared acquired documents, expiring source bundles, revision-specific embedding snapshots and published movie content. A user's quiz score or collection remains private account data. Frontend request caching is separate and does not establish evidence provenance.

**What prevents malicious actions?** Source and model text have no arbitrary shell, credential, network or database-action tools. Application code owns bounded source reads and reviewed writes. Public-network restrictions protect fetching; prompt rules, exact citations and semantic review protect outputs. These layers reduce risk; prompt-injection detection alone is not a security guarantee.

**What is still required for production?** Fresh independently labelled source/answer evaluations, stronger publisher credibility and conflict handling, wider qualified film coverage, durable distributed admission/rate limits, retention/licensing review and multi-user load tests. Free search should remain replaceable.
