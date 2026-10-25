"""Code-owned fast path for answers repeated literally in their exact citation."""
import re

POLICY = "literal-selected-answer-v1"


def normalized(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def literal_answer_support(answer: str, evidence_quote: str) -> bool:
    """True only when the complete normalized answer is contiguous in the quote.

    This is not semantic proof by itself. It is used after the structured critic
    has separately checked the question/answer relation and distractors.
    """
    if not isinstance(answer,str) or not isinstance(evidence_quote,str):
        raise ValueError("Answer support requires text")
    selected=normalized(answer);source=normalized(evidence_quote)
    if not selected or not source:return False
    return f" {selected} " in f" {source} "
