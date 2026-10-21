"""Count actual published evidence publishers, never collected-page quotas."""
from urllib.parse import urlsplit

POLICY = "two-publisher-movie-content-v1"
ADDITIONAL_MOVIES = {
    278: "The Shawshank Redemption",
    238: "The Godfather",
    680: "Pulp Fiction",
    550: "Fight Club",
    13: "Forrest Gump",
    1124: "The Prestige",
    10681: "WALL-E",
    8587: "The Lion King",
    76341: "Mad Max: Fury Road",
}

def publisher(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if host == "imsdb.com":
        return None
    if not host:
        raise ValueError("Missing evidence publisher")
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        return "wikipedia.org"
    if host in ("bbc.com", "bbc.co.uk") or host.endswith((".bbc.com", ".bbc.co.uk")):
        return "bbc.co.uk"
    parts = host.split(".")
    suffix = ".".join(parts[-2:])
    # Group common subdomains conservatively; private hosting platforms also
    # count as one host family rather than falsely proving independence.
    compound = {"co.uk", "org.uk", "com.au", "co.in", "com.br", "co.jp", "co.nz", "com.sg", "co.za"}
    return ".".join(parts[-3:] if suffix in compound else parts[-2:])

def item_publishers(items) -> list[str]:
    return sorted({p for item in items for citation in item.citations
                   if (p:=publisher(citation.source_ref)) is not None})

def coverage_record(*, fact_count: int, question_count: int, fact_publishers, quiz_publishers) -> dict:
    facts = sorted(set(fact_publishers))
    quiz = sorted(set(quiz_publishers))
    return {
        "policy": POLICY,
        "facts": {"items": fact_count, "publishers": facts},
        "quiz": {"items": question_count, "publishers": quiz},
        "complete": fact_count >= 5 and question_count >= 10 and len(facts) >= 2 and len(quiz) >= 2,
    }


def content_coverage(quiz, facts) -> dict:
    scored = [q for q in quiz.items if q.kind != "interpretation"]
    return coverage_record(
        fact_count=len(facts.items),
        question_count=len(scored),
        fact_publishers=item_publishers(facts.items),
        quiz_publishers=item_publishers(scored),
    )

def require_content_coverage(quiz, facts) -> dict:
    coverage = content_coverage(quiz, facts)
    if not coverage["complete"]:
        raise ValueError(
            "Multi-source publication needs five facts and ten questions, each bank supported by at least two publishers"
        )
    return coverage
