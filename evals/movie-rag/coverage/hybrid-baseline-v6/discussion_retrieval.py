"""Movie-scoped discussion retrieval; relevance scores do not prove support."""
from collections import Counter
import math
import re
import unicodedata

from .retrieval_learning import rank_passages, retrieve_passages

POLICY = 'discussion-hybrid-v2'
RRF_OFFSET = 60
CANDIDATES_PER_RANK = 12
STOP_WORDS = frozenset('''a an the is are was were be been am do does did why who
what which how where when with to for in on at of as and or that this he she it
his her their they we you i my our by from about s me tell please movie film
can could would should'''.split())
EVENT = re.compile(r'\b(?:plot|story|ending|end|happen(?:s|ed)?|character(?:s)?|'
                   r'rescue(?:s|d)?|escape(?:s|d)?|betray(?:s|ed)?|claim(?:s)?|blame|ferr(?:y|ies))\b')
BROAD = re.compile(r'\b(?:theme(?:s)?|symbol\w*|meaning|message|metaphor\w*|'
                   r'interpret\w*|opinion|think|represent\w*|morality|ethics|'
                   r'direct(?:or|ed|ing)?|compos\w*|score|soundtrack|music|'
                   r'film(?:ed|ing)|production|budget|revenue|cast|actor|actress|'
                   r'release|award\w*|cinematograph\w*|stunt\w*|makeup|costume\w*)\b')


def question_scope(question):
    """Restrict explicit events only; mixed, ambiguous and theme prompts stay broad.

    This English heuristic is not a learned intent/confidence classifier.
    No movie names or IDs participate in routing.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        raise ValueError('Question must be nonblank text of at most 1000 characters')
    text = question.casefold()
    return 'story' if EVENT.search(text) and not BROAD.search(text) else 'all'


def _terms(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    words = re.findall(r'[^\W\d_]+', text)
    # Match common English action plurals (claim/claims) without conflating
    # endings such as glass, status or analysis. This is deliberately modest.
    return [w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')) else w
            for w in words if len(w) > 1 and w not in STOP_WORDS]


def _lexical_ranks(question, passages, *, corpus):
    docs = [Counter(_terms(p.text)) for p in passages]
    query = set(_terms(question))
    if not docs or not query:
        return []
    # Keep movie-wide IDF when routing to a short plot: a repeated first name
    # should not become rarer than the action merely because themes were removed.
    corpus_docs = [Counter(_terms(p.text)) for p in corpus]
    frequency = Counter(word for doc in corpus_docs for word in doc)
    average = sum(sum(doc.values()) for doc in corpus_docs) / len(corpus_docs) or 1
    scores = []
    for passage, doc in zip(passages, docs):
        score = 0.
        for term in query:
            count = doc[term]
            if count:
                idf = math.log(1 + (len(corpus_docs)-frequency[term]+.5)/(frequency[term]+.5))
                score += idf*count*2.2/(count+1.2*(.25+.75*sum(doc.values())/average))
        if score > 0:
            scores.append((passage.passage_id, score))
    return sorted(scores, key=lambda pair: (-pair[1], pair[0]))


def retrieve_discussion_passages(*, question, query_vector, passages, query_model,
                                 movie_id, allow_spoilers=False, k=3, on_trace=None):
    scope = question_scope(question)
    if len(passages) > 400:
        raise ValueError('Discussion snapshot exceeds the 400-passage budget')
    # Validate k, query and every eligible vector BEFORE section routing. A
    # wrong model/vector must not be silently hidden by a topic filter.
    retrieve_passages(query_vector, passages, query_model=query_model, movie_id=movie_id,
                      allow_spoilers=allow_spoilers, k=k)
    eligible = [p for p in passages if p.movie_id == movie_id
                and (allow_spoilers or p.spoiler_status == 'safe')]
    classified = any(p.section_title != 'Unclassified' for p in eligible)
    pool = [p for p in eligible if p.section_category == 'plot'] if scope == 'story' and classified else eligible
    dense = rank_passages(query_vector, pool, k=len(pool)) if pool else []
    lexical = _lexical_ranks(question, pool, corpus=eligible)
    vector_rank = {h.passage.passage_id: index+1 for index, h in enumerate(dense)}
    word_rank = {identifier: index+1 for index, (identifier, _) in enumerate(lexical)}
    candidate_ids = set(list(vector_rank)[:CANDIDATES_PER_RANK] + list(word_rank)[:CANDIDATES_PER_RANK])
    fused = {identifier: 1/(RRF_OFFSET+vector_rank[identifier])
             + (1/(RRF_OFFSET+word_rank[identifier]) if identifier in word_rank else 0)
             for identifier in candidate_ids}
    ordered = sorted(candidate_ids, key=lambda identifier: (-fused[identifier], identifier))
    selected = ordered[:k]
    anchor = lexical[0][0] if lexical else None
    if anchor is not None and anchor not in selected:
        # Keep one strong exact-word candidate even when semantic commentary
        # outranks it. It remains evidence to inspect, never a guaranteed answer.
        selected = selected[:k-1] + [anchor]
        selected.sort(key=lambda identifier: (-fused[identifier], identifier))
    by_id = {h.passage.passage_id: h for h in dense}
    if on_trace is not None:
        on_trace({'policy': POLICY, 'scope': scope, 'classified': classified,
                  'eligible_passages': len(eligible), 'routed_passages': len(pool),
                  'lexical_anchor': anchor, 'selected_ids': selected,
                  'vector_top': [{'id': h.passage.passage_id, 'cosine': h.score} for h in dense[:CANDIDATES_PER_RANK]],
                  'lexical_top': [{'id': identifier, 'bm25': score} for identifier, score in lexical[:CANDIDATES_PER_RANK]],
                  'selected_ranks': [{'id': identifier, 'rrf': fused[identifier],
                                      'vector_rank': vector_rank[identifier],
                                      'lexical_rank': word_rank.get(identifier)} for identifier in selected]})
    # Preserve the RetrievalHit contract: score is cosine, NOT the RRF value
    # and not a probability. The trace explains the final mixed ordering.
    return [by_id[identifier] for identifier in selected]
