"""Small development smoke grader; human review is required for claim support."""

from .grounding_learning import GroundedAnswer


def check_answer(case: dict, answer: GroundedAnswer) -> list[str]:
    failures = []
    if answer.status != case["expected_status"]:
        failures.append(f"Expected status {case['expected_status']}, got {answer.status}")
    if set(answer.citation_ids) != set(case["expected_citation_ids"]):
        failures.append("Citations differ from labelled expected IDs")
    text = answer.answer.casefold()
    for alternatives in case["required_phrase_groups"]:
        if not any(phrase.casefold() in text for phrase in alternatives):
            failures.append(f"Missing expected phrase group: {alternatives}")
    for phrase in case["forbidden_phrases"]:
        if phrase.casefold() in text:
            failures.append(f"Forbidden output marker: {phrase}")
    return failures
