"""Deterministic shape rules for exact-source quiz answers."""

from dataclasses import dataclass
import re


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9’'\-]*")
LEADING_CONNECTORS = {"and", "but", "or", "nor", "so", "yet", "therefore"}
LEADING_RELATIVES = {"who", "whom", "whose", "which", "that"}
TRAILING_FRAGMENTS = {
    "and",
    "but",
    "or",
    "nor",
    "to",
    "of",
    "for",
    "with",
    "by",
    "from",
    "in",
    "on",
    "at",
    "into",
    "a",
    "an",
    "the",
    "his",
    "her",
    "their",
    "who",
    "whom",
    "whose",
    "which",
    "that",
}
NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "dozen",
    "hundred",
    "thousand",
    "million",
}
DURATION_WORDS = {
    "second",
    "seconds",
    "minute",
    "minutes",
    "hour",
    "hours",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "decade",
    "decades",
}
GENERIC_WORDS = {
    "a",
    "an",
    "the",
    "he",
    "she",
    "it",
    "they",
    "this",
    "that",
    "these",
    "those",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
}


@dataclass(frozen=True)
class BriefConstraints:
    """Only exclusions stated explicitly by a replacement brief."""

    omit_quantities: bool = False
    avoid_identity_only: bool = False


def parse_brief_constraints(brief: str) -> BriefConstraints:
    if not isinstance(brief, str):
        raise TypeError("Replacement brief must be text")
    text = brief.casefold()
    return BriefConstraints(
        omit_quantities=bool(
            re.search(
                r"\bomit\b.{0,30}\b(?:duration|count|number|years?)\b", text
            )
        ),
        avoid_identity_only=bool(
            re.search(r"\b(?:rather than|not)\b.{0,30}\bname\b", text)
        ),
    )


def _tokens(span: str) -> list[str]:
    return [match.group() for match in TOKEN_RE.finditer(span)]


def answer_span_problems(span: str, *, brief: str) -> list[str]:
    """Return stable rejection reasons without changing the source span."""
    if not isinstance(span, str):
        raise TypeError("Answer span must be text")
    words = _tokens(span)
    lowered = [word.casefold() for word in words]
    problems = []
    if len(words) < 2:
        problems.append("too_short")
    if len(words) > 12:
        problems.append("too_long")
    if lowered and lowered[0] in LEADING_CONNECTORS:
        problems.append("leading_connector")
    if lowered and lowered[0] in LEADING_RELATIVES:
        problems.append("leading_relative")
    if lowered and (
        lowered[-1] in TRAILING_FRAGMENTS
        or lowered[-1].endswith(("'s", "’s"))
    ):
        problems.append("trailing_fragment")
    if (
        span.count("(") != span.count(")")
        or span.count("[") != span.count("]")
        or span.count("{") != span.count("}")
        or span.count('"') % 2
        or span.count("“") != span.count("”")
    ):
        problems.append("unmatched_punctuation")

    constraints = parse_brief_constraints(brief)
    if constraints.omit_quantities and any(
        word.isdigit() or word in NUMBER_WORDS or word in DURATION_WORDS
        for word in lowered
    ):
        problems.append("forbidden_quantity")

    significant = [
        word for word in words if word.casefold() not in {"a", "an", "the"}
    ]
    if (
        constraints.avoid_identity_only
        and significant
        and all(word[:1].isupper() for word in significant)
    ):
        problems.append("identity_only")
    if lowered and all(word in GENERIC_WORDS for word in lowered):
        problems.append("meaningless_content")
    return list(dict.fromkeys(problems))


def answer_shape_score(span: str) -> float:
    """Prefer concise standalone phrases; factual relevance is scored elsewhere."""
    words = _tokens(span)
    score = 5.0 - abs(len(words) - 5) * 0.35
    if words and words[0].casefold() in {"to", "by", "through", "after"}:
        score += 0.5
    return round(score, 4)
