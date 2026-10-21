# Production guidelines

Agreed direction, 11 October 2026. These are deployment goals, not claims that all components already exist.

## Catalog and discovery

The initial 1,500-film catalog is a seed, not a discovery limit. Persist lightweight metadata for seeded, discovered and visited films using TMDB IDs. Fetch detailed credits, characters, production data, trailers and watch options as needed; preserve last-good metadata and refresh it according to field freshness. Store image paths/URLs rather than duplicating poster files by default.

Search should combine local matches with bounded TMDB title/person discovery in one paginated list, deduplicated by ID. Consult external discovery even when local matches exist. Resolve actor/director searches through verified people and their appropriate movie credits. Description-keyword search covers stored descriptions; TMDB title/person discovery does not imply global description full-text search. Cache repeated queries, control provider concurrency and respect rate-limit responses. Distinguish provider failure from no matches.

Metadata count can grow with demand; there is no fixed production cap of 1,500. Fetching metadata does not imply a movie has prepared AI content. Full-provider replication is not required. TMDB daily ID exports are identifiers/basic attributes, not full metadata exports.

## Shared content and personal activity

Facts, quiz questions, source evidence and generation versions belong to the movie, with language/version distinctions when needed. Prepare popular movies beforehand and other movies in response to demand. Coalesce concurrent requests into one logical preparation job. Verified content is persisted and ordinary reads do not invoke an LLM.

Keep quiz attempts, scores, seen-question IDs, spoiler preferences and collections separate per user. Draw different quiz rounds from a shared bank; request controlled shared-bank expansion when appropriate. Personal discussion history is separate; public posting requires explicit user intent.

Quiz evidence concerns the released film's story; background facts concern filmmaking/news rather than plot. Scripts retain draft/version metadata and cannot override final-film evidence. Preparation may fail to reach five facts/ten questions when sources are insufficient. Never fabricate to meet a count.

## Preparation and deployment

Durable jobs need atomic enqueue/claim, duplicate suppression, bounded retries, worker ownership, restart recovery, evidence/policy-pinned checkpoints and idempotent publication. Existing reviewed content stays available until a replacement passes verification. Drafts remain internal; no consumer draft workspace.

Facts and quizzes can eventually have independent readiness/refresh schedules. Historical production facts change infrequently; news and provider metadata may need more frequent updates. Retain provenance, corrections and version history.

Ollama runs on our server/worker host. Inference concurrency follows measured hardware limits; page views serve saved data independently. Account-backed personal storage is now implemented locally; temporary guest saves clear on refresh, and new accounts require email verification. Public deployments must replace loopback email previews with configured SMTP/TLS delivery. Scalable search/indexing, independent factual evaluations and catalog-wide qualified automatic generation remain future work. Current internal draft jobs do not authorize autonomous publication.

## References

- [TMDB search and details](https://developer.themoviedb.org/docs/search-and-query-for-details)
- [TMDB daily ID exports](https://developer.themoviedb.org/docs/daily-id-exports)
- [TMDB rate limiting](https://developer.themoviedb.org/docs/rate-limiting)
- [Ollama concurrency](https://docs.ollama.com/faq)
- [Safe retries and idempotency](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
