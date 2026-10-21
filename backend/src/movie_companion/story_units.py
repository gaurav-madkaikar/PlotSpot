"""Small, exactly attributed plot units for question-focused quiz retrieval."""
import re

BOUNDARY = re.compile(r'[.!?](?:\[[^\]\n]+\])*(?::\s*[0-9–-]+)?\s+(?=[A-Z“"])')
CONTEXT_START = re.compile(r'^(?:He|She|They|It|His|Her|Their|This|These|After|Before|However|Meanwhile|Attempting)\b')


def score_ranks(scores):
    """Descending competition ranks; equal scores share a rank."""
    ranks, previous, shared_rank = {}, None, 0
    for rank,index in enumerate(sorted(range(len(scores)),key=lambda i:(-scores[i],i))):
        if scores[index] != previous:
            shared_rank = rank
        ranks[index] = shared_rank
        previous = scores[index]
    return ranks


def quiz_units(pool):
    """Split validated plot groups, keeping preceding context for pronouns.

    Origins always refer to unchanged source bytes. This is a retrieval aid,
    not an assertion that a sentence supports a valid question.
    """
    units, seen = [], set()
    for text, origin in pool:
        boundaries = [0, *[m.end() for m in BOUNDARY.finditer(text)], len(text)]
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            raw = text[start:end]
            sentence = raw.strip()
            if len(sentence) < 20:
                continue
            if index and CONTEXT_START.match(sentence):
                previous = boundaries[index - 1]
                if end - previous <= 600:
                    start, raw = previous, text[previous:end]
            value = raw.strip()
            offset = origin.start + start + len(raw) - len(raw.lstrip())
            key = (offset, offset + len(value))
            if len(value) <= 600 and key not in seen:
                seen.add(key)
                units.append((value, origin.model_copy(update={'start': key[0], 'end': key[1]})))
    return units
