# Background article development checks

This folder records local RAG proposal inspections, an explicit assistant-reviewed selection, publication verification and cache reuse. It is not an unseen-movie benchmark or evidence of automatic publication safety.

Two reviewed sources were used: [TIME's Arrival filmmaker interview](https://time.com/4677598/arrival-oscar-cinematography/) and [BFI's Villeneuve craft article](https://www.bfi.org.uk/features/strange-new-worlds-craft-denis-villeneuve). The latter discusses multiple movies; only its reviewed Arrival music paragraph is ingested. Full HTML remains in ignored private caches. Publication dates are 2017-02-22 and 2021-09-22, distinct from retrieval dates.

| Inspection | Proposed | Eligible for review | Errors | Published by inspection |
| --- | ---: | ---: | ---: | --- |
| v1 | 3 | 1 | 0 | No |
| v2 | 4 | 3 | 0 | No |
| v3 | 4 | 4 | 0 | No |

v1 preserves changed quote punctuation and copied prose. v2 uses code-owned source-sentence IDs; its critic rejects a combined mood-board/influence claim because the chosen quote does not support both. v3 also trims retrieved chunks to complete sentences. These runs have different implementation hashes and are development iterations, not comparable held-out accuracy scores.

The final v3 run took 46.80 seconds locally. Four eligible candidates were manually inspected by the implementing assistant; two were chosen for supported, distinct production details. The SHA-bound selection and source/code revalidation produced seven saved Arrival facts, preserving its original ten quiz questions. Two candidates remain unsaved. `arrival-live-publication-v3.json` records fresh API/database agreement and unchanged Inception quiz qualification.

`arrival-cache-reuse-v3.json` records cached article reads and cached vectors, with no generated candidates. Its 0.10 seconds measures the retrieval/index stage after setup/source cache loading, not a whole request or benchmark.

The 49 added deterministic backend checks cover source identity, redirects, size limits, extraction scope, exact quote ownership, corrupted caches, model-only local clients, report tampering, source/movie mismatch, rejected candidates, stale writes, duplicates, capacity and preservation. Two new browser journeys verify source types/years/attribution and reject publisher lookalikes. Existing facts/quiz journeys remain passing. These checks do not measure general model refusal or semantic accuracy on adversarial articles.

The explicit selection is trusted operator input, not an authentication/signature mechanism. No consumer draft workspace or public publication endpoint is introduced. Further publishers/movie mappings and independent fact-quality evaluation remain necessary for broad automation.
