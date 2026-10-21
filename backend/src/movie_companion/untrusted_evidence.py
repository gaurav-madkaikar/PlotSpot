"""Create a model-facing story view without changing stored source evidence."""
import re


_DIRECTIVE = re.compile(
    r"(?:\b(?:system|developer|assistant|model)\s+(?:override|message|instruction|prompt)\b"
    r"|\bignore\s+(?:all|any|the|previous)\s+(?:instructions?|conflicts?|polic(?:y|ies)|sources?)\b"
    r"|\b(?:approve|accept|grade|mark)\s+(?:every|all|this|the)\s+(?:items?|candidates?|answers?|response)\b"
    r"|\breturn\s+(?:supported|agrees|accepted)\b"
    r"|\b(?:read|reveal|send|upload|post|exfiltrate)\b.{0,80}\b(?:\.env|secrets?|credentials?|api[-_ ]?keys?)\b"
    r"|\b(?:secrets?|credentials?|api[-_ ]?keys?)\b.{0,80}\b(?:https?://|webhook|server)\b"
    r"|\[/?inst\]|<\/?system>|begin\s+system\s+prompt)",
    re.IGNORECASE | re.DOTALL,
)


def model_story_evidence(text: str) -> str:
    """Drop only high-confidence instruction segments from a model-facing copy.

    The original text remains authoritative for provenance and literal-quote checks.
    If a source mixes an instruction marker into a story sentence, the whole segment
    is removed and downstream review can safely abstain.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Nonempty source evidence is required")
    segments = re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
    retained = [segment.strip() for segment in segments
                if segment.strip() and not _DIRECTIVE.search(segment)]
    return " ".join(retained)
