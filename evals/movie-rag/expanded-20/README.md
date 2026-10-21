# Expanded twenty-film publication

This directory separates pre-publication review evidence from committed publication evidence and the reproducible post-publication audit.

- `final-review-audit.json` records the final frozen review set. `final-review-audit-v2.json` preserves the earlier audit before the Arrival display-title cleanup.
- `publication-receipts.json` records the twenty atomic content writes.
- `published-content-audit.json` recomputes receipt, payload, quota and publisher-diversity checks from the live shared database.
- `published-content-audit.md` presents the same results for a reviewer.
- `batch-status.json` is a historical pre-publication batch snapshot; its `needs_review` states are not current job states.

Run `backend/.venv/bin/python backend/scripts/audit_published_movie_content.py` from the repository root to refresh the two published-content audit files. A passing result establishes storage integrity and configured readiness. It does not establish semantic accuracy, publisher credibility, safety under every attack or production throughput.
