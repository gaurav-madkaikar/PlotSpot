"""Complete source sentences with bounded, original-window citation provenance."""
from dataclasses import dataclass
import re

from .retrieval_learning import EmbeddedPassage, RetrievalHit
from .sentence_spans import complete_sentence_spans
from .vector_math import cosine_similarity
from .passage_location import PassageLocation

POLICY = 'discussion-sentence-context-v2'


@dataclass(frozen=True)
class SupportOption:
    text: str
    citation_ids: tuple[str, ...]
    identity_context: bool = False


def validate_location(p: EmbeddedPassage):
    loc = p.location
    if loc is None:
        return
    if (not isinstance(loc, PassageLocation) or not isinstance(loc.source_key, str)
            or not re.fullmatch(r'[a-f0-9]{64}', loc.source_key)
            or not re.fullmatch(re.escape(loc.source_key[:32])+r'_\d{3}', p.passage_id)
            or (loc.movie_id, loc.source_label, loc.spoiler_status, loc.section_title, loc.section_category)
            != (p.movie_id, p.source_label, p.spoiler_status, p.section_title, p.section_category)
            or not isinstance(loc.text, str) or len(loc.text) > 100000
            or any(type(n) is not int for n in (loc.start, loc.end, loc.section_start, loc.section_end))
            or not 0 <= loc.section_start <= loc.start < loc.end <= loc.section_end <= len(loc.text)
            or loc.text[loc.start:loc.end] != p.text):
        raise ValueError('Discussion source location mismatch')


def _cover(start, end, pool):
    """Greedy interval coverage; no gap, unauthorized text or guessed overlap."""
    cursor, contributors = start, []
    while cursor < end:
        candidates = [p for p in pool if p.location.start <= cursor < p.location.end]
        if not candidates:
            return ()
        chosen = min(candidates, key=lambda p: (-p.location.end, p.passage_id))
        contributors.append(chosen.passage_id)
        cursor = chosen.location.end
        if len(contributors) > 3:
            return ()
    return tuple(contributors)


def build_discussion_context(hits, passages, *, movie_id, allow_spoilers, query_vector, on_trace=None, question=""):
    """Return <=6 generation windows and <=36 exactly attributed options.

    The top-three anchors remain unchanged. Only eligible windows with validated
    offsets from the same source/section may complete an overlapping sentence.
    No stored passage text, vector, ID or snapshot identity is rewritten.
    """
    eligible = [p for p in passages if p.movie_id == movie_id
                and (allow_spoilers or p.spoiler_status == 'safe')]
    for p in eligible:
        validate_location(p)
    by_id = {p.passage_id: p for p in eligible}
    generation = {h.passage.passage_id: h for h in hits}
    if not set(generation) <= set(by_id) or len(generation) > 3:
        raise ValueError('Context anchors must be eligible top-three evidence')
    if any(h.passage != by_id[h.passage.passage_id] for h in hits):
        raise ValueError('Context anchor differs from validated evidence')
    options, seen, spans = [], set(), {}
    for hit in hits:
        anchor, loc = hit.passage, hit.passage.location
        if loc is None:
            # Complete authored learning fixtures remain usable without offsets;
            # no neighboring context is guessed for these records.
            candidates = [(anchor.text[a:b], (anchor.passage_id,))
                          for a, b in complete_sentence_spans(anchor.text)]
        else:
            key = (loc.source_key, loc.section_start, loc.section_end)
            if key not in spans:
                body = loc.text[loc.section_start:loc.section_end]
                spans[key] = [(loc.section_start+a, loc.section_start+b)
                              for a, b in complete_sentence_spans(body)]
            pool = [p for p in eligible if p.location is not None
                    and (p.location.source_key, p.location.section_start, p.location.section_end) == key
                    and p.location.text == loc.text and p.embedding_model == anchor.embedding_model]
            candidates = [(loc.text[a:b], _cover(a, b, pool)) for a, b in spans[key]
                          if min(b, loc.end)-max(a, loc.start) >= 20]
        for text, ids in candidates:
            if not 20 <= len(text) <= 600 or not ids or text in seen:
                continue
            if len(set(generation) | set(ids)) > 6:
                continue
            seen.add(text)
            options.append(SupportOption(text, ids))
            for identifier in ids:
                generation.setdefault(identifier, RetrievalHit(by_id[identifier],
                    cosine_similarity(query_vector, by_id[identifier].vector)))
            if len(options) == 36:
                break
        if len(options) == 36:
            break
    # Full-name context is a lexical heuristic, not a model-authored alias map.
    identity = _identity_context(question, hits, eligible)
    if identity is not None and len(set(generation) | set(identity.citation_ids)) <= 6:
        options = [identity] + [o for o in options if o.text != identity.text][:35]
        for identifier in identity.citation_ids:
            generation.setdefault(identifier, RetrievalHit(by_id[identifier],
                cosine_similarity(query_vector, by_id[identifier].vector)))
    if on_trace is not None:
        on_trace({'type': 'context', 'policy': POLICY,
                  'anchor_ids': [h.passage.passage_id for h in hits],
                  'generation_ids': list(generation), 'options': len(options),
                  'identity_context_ids': list(identity.citation_ids) if identity is not None
                      and any(o.identity_context for o in options) else []})
    return list(generation.values()), options


def validate_support_option(option, hits):
    if (not isinstance(option, SupportOption) or type(option.identity_context) is not bool
            or not isinstance(option.text, str)
            or not 20 <= len(option.text) <= 600 or not isinstance(option.citation_ids, tuple)
            or not all(isinstance(i, str) for i in option.citation_ids)
            or not 1 <= len(option.citation_ids) <= 3
            or len(set(option.citation_ids)) != len(option.citation_ids)):
        raise ValueError('Invalid support option')
    by_id = {h.passage.passage_id: h.passage for h in hits}
    if not set(option.citation_ids) <= set(by_id):
        raise ValueError('Support option outside generation evidence')
    pool = [by_id[i] for i in option.citation_ids]
    for p in pool:
        validate_location(p)
    if all(p.location is None for p in pool):
        if len(pool) != 1 or option.text not in pool[0].text:
            raise ValueError('Fixture quote is outside its evidence')
        return
    loc = pool[0].location
    if loc is None or any(p.location is None or
            (p.location.source_key, p.location.section_start, p.location.section_end, p.location.text)
            != (loc.source_key, loc.section_start, loc.section_end, loc.text) for p in pool):
        raise ValueError('Support option mixes source contexts')
    for match in re.finditer(re.escape(option.text), loc.text):
        a, b = match.span()
        if (loc.section_start <= a < b <= loc.section_end and _cover(a, b, pool)
                and all(min(b, p.location.end) > max(a, p.location.start) for p in pool)):
            return
    raise ValueError('Support quote is not covered by cited source windows')


def _identity_context(question, hits, eligible):
    """One unambiguous adjacent proper-name pair in the same source/section.

    One token must occur in the question, and a different token in an
    anchor. Exact source sentences carry the context;
    no name substitutions or externally remembered aliases are asserted.
    """
    words = lambda text: {w.casefold() for w in re.findall(r"[A-Za-z]{3,}", text)}
    qwords = words(question)
    ignored = {'the', 'what', 'why', 'how', 'who', 'when', 'where', 'which',
               'does', 'did', 'and', 'are', 'was', 'were', 'has', 'have', 'will',
               'movie', 'film', 'story', 'about', 'his', 'her', 'their', 'they',
               'after', 'before', 'with', 'from', 'for', 'this', 'that',
               'linguist', 'colonel', 'doctor', 'captain', 'detective', 'professor',
               'officer', 'agent', 'general', 'president', 'king', 'queen', 'prince'}
    matches, scanned = [], set()
    for hit in hits:
        loc = hit.passage.location
        if loc is None:
            continue
        key = (loc.source_key, loc.section_start, loc.section_end)
        if key in scanned:
            continue
        scanned.add(key)
        anchors = [h.passage for h in hits if h.passage.location is not None and
                   (h.passage.location.source_key, h.passage.location.section_start,
                    h.passage.location.section_end) == key]
        awords = words(' '.join(p.text for p in anchors))
        pool = [p for p in eligible if p.location is not None and
                (p.location.source_key, p.location.section_start, p.location.section_end) == key
                and p.location.text == loc.text and p.embedding_model == hit.passage.embedding_model]
        body = loc.text[loc.section_start:loc.section_end]
        for a,b in complete_sentence_spans(body):
            text = body[a:b]
            if not 20 <= len(text) <= 600:
                continue
            for name in re.findall(r"\b[A-Z][a-z]{2,}(?:[-'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]{2,}(?:[-'][A-Z]?[a-z]+)?){1,3}", text):
                tokens = re.findall(r"[A-Za-z]{3,}", name)
                for first,second in zip(tokens,tokens[1:]):
                    pair = (first.casefold(),second.casefold())
                    if set(pair) & ignored:
                        continue
                    if not any(x in qwords and y in awords and x != y
                               for x,y in (pair,pair[::-1])):
                        continue
                    ids = _cover(loc.section_start+a, loc.section_start+b, pool)
                    if ids:
                        matches.append((pair,SupportOption(text,ids,True)))
    # Multiple different name pairs, even across anchors, require more context;
    # never guess that two people sharing a first or last name are the same.
    if len({pair for pair,_ in matches}) != 1:
        return None
    return matches[0][1]
