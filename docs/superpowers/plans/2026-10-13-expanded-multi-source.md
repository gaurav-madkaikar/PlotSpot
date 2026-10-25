# Twenty-film Multi-source Implementation Plan

**Goal:** Complete and inspect reusable multi-source content for the approved twenty movies.
**Architecture:** Explicit publisher-coverage policy, bounded corroboration, existing source acquisition/RAG/research review and atomic publication, with a resumable operator batch runner.
**Tech Stack:** Python/FastAPI, SQLite/Chroma, local Ollama, DDGS/httpx, pytest.

## Global constraints

Twenty movies total; minimum five facts and ten scored quiz questions per published movie. Two non-script publishers per facts bank and per scored quiz bank. Screenscripts remain optional draft context, excluded from facts and sole answer authority. User authorization covers local generation, assistant source review and reversible publication. Keep existing banks until each replacement/enrichment passes review. Preserve account/community/member/spoiler boundaries; no unrelated UI changes.

- [ ] Task 1: Add coverage policy in `source_coverage.py`; extend the fixed movie registry to the approved twenty; enforce publication diversity for reports opting into the new policy. Test distinct publishers, script exclusion, strict incomplete preservation and legacy compatibility in `test_source_coverage.py`.
- [ ] Task 2: Add bounded source corroboration for discussion in `multi_source_pipeline.py`/`source_corroboration.py`, with exact citations and explicit abstention when two publishers cannot support the answer. Test independently supported answers and missing/irrelevant/cross-movie evidence in `test_multi_source_pipeline.py`.
- [ ] Task 3: Add resumable acquisition/preparation/publication batch tooling in `backend/scripts/prepare_movie_batch.py`, per-film checkpoints and pinned selections. Acquire the twenty identities/Wikipedia/web/script sources, preserving real coverage and expected failures. Freeze source/workflow identities during model runs; review candidate quotes/options/purpose/novelty before publishing explicit selections. Backup the existing public bank before writes.
- [ ] Task 4: Generate/enrich the approved twenty-film content, repair failures exposed by measured output, then validate actual saved source diversity and representative discussion answers. Run relevant tests/full backend checks/frontend build. Record complete/incomplete counts, source gaps, actual model outcomes, publication receipts and learning explanation in `expanded-20` reports and Lesson 72. Restart the local API and inspect representative live member content without altering user history.

Self-review: source collection is not publication diversity; scripts and duplicate publisher pages cannot inflate counts. Correct quotations are not sufficient semantic support. Local model work stays serial and private account data is never sent to search. Expected provider/model failures persist useful validated work and never authorize fake successful banks.
