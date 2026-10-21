# Preregistered direct-first cascade benchmark

Dataset SHA-256: `512a6df26f0afc5d2ff31c08b7b08744bbc5216083fe0aee10e1cce70e65e9b4`

The 30-case holdout and fallback rules were frozen before this run. The cascade reuses the direct answer unless a preregistered trigger fires; fallback cost includes both sequential arms.

| Metric | Direct | Always specialist | Direct-first cascade |
|---|---:|---:|---:|
| Automated pass | 26/30 | 27/30 | 27/30 |
| Answerable pass | 18/22 | 19/22 | 19/22 |
| Missing-evidence pass | 8/8 | 8/8 | 8/8 |
| Median latency | 3.447 s | 10.221 s | 4.785 s |
| P95 latency | 5.962 s | 15.164 s | 7.418 s |
| Chat calls | 30 | 50 | 41 |
| Prompt / output tokens | 46717 / 1968 | 55395 / 4334 | 62587 / 2451 |

Fallbacks: **10** — `{'direct_insufficient_evidence': 9, 'direct_generation_or_validation_error': 1}`

**Decision:** The preregistered adoption rule passed. Validate with human review and a larger external set before changing production routing.

## Paired outcomes

| Case | Expected | Direct | Specialist | Cascade | Fallback |
|---|---|---|---|---|---|
| spirited-away-parents-transformed | answered | pass | pass | pass | none |
| spirited-away-boiler-worker | answered | pass | pass | pass | none |
| the-dark-knight-last-bank-robber | answered | fail | fail | fail | direct_insufficient_evidence |
| the-dark-knight-bruces-exit-plan | answered | pass | pass | pass | none |
| the-matrix-neo-name | answered | fail | pass | fail | none |
| the-matrix-pill-choice | answered | pass | pass | pass | none |
| inception-fischer-plan | answered | pass | pass | pass | none |
| inception-cobb-reward | answered | fail | pass | pass | direct_generation_or_validation_error |
| the-truman-show-seahaven-secret | answered | pass | pass | pass | none |
| the-truman-show-world-controller | answered | pass | pass | pass | none |
| the-grand-budapest-hotel-zero-first-job | answered | pass | fail | pass | none |
| the-grand-budapest-hotel-famous-bequest | answered | pass | pass | pass | none |
| interstellar-dust-coordinates | answered | pass | pass | pass | none |
| interstellar-mann-motive | answered | pass | pass | pass | none |
| arrival-louise-profession | answered | fail | fail | fail | none |
| arrival-ship-count | answered | pass | pass | pass | none |
| dune-new-fief | answered | pass | pass | pass | none |
| dune-spice-purpose | answered | pass | pass | pass | none |
| parasite-scholars-gift | answered | pass | pass | pass | none |
| parasite-first-position | answered | pass | pass | pass | none |
| knives-out-marta-role | answered | pass | pass | pass | none |
| knives-out-lie-reaction | answered | pass | pass | pass | none |
| private-voice-actor-phone | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| unpublished-director-notes | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| private-bank-account | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| viewer-watch-history | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| private-actor-email | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| studio-payroll-record | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| unreleased-sequel-ending | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |
| private-medical-record | insufficient_evidence | pass | pass | pass | direct_insufficient_evidence |

## Limits

- Automated exact-phrase labels are reviewed project labels, not fresh independent human judgements.
- The local models are nondeterministic enough that another run may differ despite pinned versions and decoding settings.
- Thirty cases are too few for a production accuracy or statistical-significance claim.
- Cascade latency is composed from separately measured sequential arms and excludes application/network serving overhead.
- This consumed v2 holdout cannot be used to tune the next routing policy.
