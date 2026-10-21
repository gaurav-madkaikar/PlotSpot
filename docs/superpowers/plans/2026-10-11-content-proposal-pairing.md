# Movie navigation and local proposal pairing

User approved the next guided Ollama proposal slice and requested navigation changes first.

**Design:** Four movie links (About/Facts/Quiz/Discuss); About contains overview, cast, creative credits, film details and watch availability. Preserve legacy #cast subsection targets and return URL state. Style the return link as a rounded, accessible light control. No data/API changes for navigation.

**AI pairing:** Define a bounded evidence envelope and strict fact/question proposal schemas. Learner implements only `propose_content` (prompt, existing `chat_once` call, structured parsing). Assistant supplies read-only local runner, deterministic evidence checks and worked-example lesson. Draft proposals remain separate from publication; no automatically generated claims are saved. No LangChain or new dependencies.

- [x] Implement navigation and return-link styling; update regression expectations.
- [x] Define evidence/proposal contracts and support-check helpers, with schema/isolation tests.
- [x] Add learner-owned function stub and local runner using existing reviewed saved evidence and verified local Ollama model.
- [x] Explain the exercise, example API flow, limitations and next integration step in learning note 36.
- [x] Validate build/browser/backend contracts, restore live servers and save UI preview.

Validation: production build, all 51 browser journeys and 472 backend checks passed. Live About view contains cast/details, the return link uses the rounded light control and four section links are visible. Legacy #cast behavior covered by regression tests. Saved preview `.cache/previews/movie-about-return.png`; live servers restored. The learner function remains intentionally unfinished and unconnected to routes; no successful real proposal/model-generation run is claimed yet.

Later: review the learner's implementation, run real Ollama proposals, evaluate claim/option quality, then connect bounded preparation jobs. No production route will depend on an unfinished exercise.

## Ownership update

User requested on the subsequent turn that the assistant perform all implementation/checks moving forward. Learner ownership/stub requirements above are superseded. Complete the proposal call, preserve teaching notes, add independent draft review and labelled development checks, and run actual local models before integrating publication jobs. Model review does not grant automatic publication permission.
