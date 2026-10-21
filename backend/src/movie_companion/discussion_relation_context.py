"""Recover one missing-detail sentence from the already validated option pool."""
from .discussion_retrieval import _terms


def supplemental_option(answer, options, selected_quotes):
    """Lexical coverage heuristic, not an entailment decision.

    Require two answer terms absent from selected evidence, both explicitly
    present in another complete offered sentence. Never fetch/rewrite a source
    or add multiple speculative contexts. The semantic reviewer still decides.
    """
    answer_terms = set(_terms(answer))
    covered = set(_terms(' '.join(selected_quotes)))
    missing = answer_terms - covered
    if len(missing) < 2:
        return None
    candidates = []
    for index, option in enumerate(options):
        if option.text in selected_quotes or option.identity_context:
            continue
        terms = set(_terms(option.text))
        found = missing & terms
        if len(found) >= 2:
            candidates.append((len(found),len(answer_terms & terms),-len(terms),-index,option))
    return max(candidates, key=lambda c:c[:4])[-1] if candidates else None
