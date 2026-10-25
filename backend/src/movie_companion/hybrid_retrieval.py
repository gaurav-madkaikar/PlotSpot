"""Bounded lexical + vector candidates, pairwise relevance, and cached ranking.

There is no lexical admission gate. Every eligible movie can enter through
semantic ranking; the reranker decides which candidates justify a result.
"""
import asyncio
from collections import Counter, OrderedDict
import math
import logging
from time import monotonic

from .search_intent import STOP_WORDS, normalize_search_text, stem, SUPERHERO_EVIDENCE, interpret
from .search_reranker import CONFIG_VERSION
from .vector_math import cosine_similarity


MINIMUM_SCORE = 2 / 3  # Development calibration is recorded in evals/discovery.


def retrieval_text(movie):
    keywords = list(getattr(movie, 'keywords', []))[:15]
    # Compatibility cue for snapshots prepared before provider keywords existed.
    if SUPERHERO_EVIDENCE.search(normalize_search_text(movie.title + ' ' + movie.overview)):
        keywords.append('superhero')
    return '\n'.join([
        f'Title: {movie.title}', f'Alternative titles: {", ".join(getattr(movie, "alternative_titles", [])[:4])}',
        f'Genres: {", ".join(movie.genres)}', f'Keywords: {", ".join(keywords)}',
        f'Synopsis: {movie.overview[:600]}',
    ])


def terms(text):
    return [stem(w) for w in normalize_search_text(text).split() if w not in STOP_WORDS and len(w) >= 3]


def lexical_ranks(movies, query):
    """BM25 gives rare matching terms more weight than ubiquitous ones."""
    documents = [Counter(terms(retrieval_text(m))) for m in movies]
    query_terms = set(terms(query))
    query_terms.update(interpret(query).required_themes)
    if not documents or not query_terms:
        return []
    frequency = Counter(t for doc in documents for t in doc)
    average = sum(sum(doc.values()) for doc in documents) / len(documents) or 1
    scored = []
    for movie, doc in zip(movies, documents):
        length = sum(doc.values())
        score = 0.0
        for term in query_terms:
            tf = doc[term]
            if tf:
                idf = math.log(1 + (len(documents) - frequency[term] + .5) / (frequency[term] + .5))
                score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * length / average))
        if score > 0:
            scored.append((movie.id, score))
    return [mid for mid, _ in sorted(scored, key=lambda item: (-item[1], item[0]))]


class HybridRetriever:
    def __init__(self, reranker, *, minimum_score=MINIMUM_SCORE):
        self.reranker = reranker
        self.minimum_score = minimum_score
        self.cache = OrderedDict()
        self.pending = {}
        self.slot = asyncio.Lock()
        self.last_trace = None

    async def rank(self, service, movies, vectors, query, fingerprint):
        key = (fingerprint, CONFIG_VERSION, getattr(self.reranker, 'model', 'test'), self.minimum_score, query, tuple(m.id for m in movies))
        cached = self.cache.get(key)
        if cached and cached[0] > monotonic():
            self.cache.move_to_end(key)
            self.last_trace = cached[2]
            return cached[1]
        self.cache.pop(key, None)
        task = self.pending.get(key)
        if task is None:
            if self.slot.locked() or self.pending:
                from .semantic_search import DiscoveryError
                raise DiscoveryError(409, 'Another search is running. Try again shortly.')
            task = asyncio.create_task(self._rank(service, movies, vectors, query, key))
            self.pending[key] = task
            def finished(completed):
                self.pending.pop(key, None)
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(finished)
        ids, trace = await asyncio.shield(task)
        self.last_trace = trace
        return ids

    async def _rank(self, service, movies, vectors, query, key):
        from .semantic_search import DiscoveryError
        async with self.slot:
            if not movies:
                return [], {'candidate_ids': [], 'scores': []}
            async def vector_ranks():
                vector = await service.query_vector(query, len(next(iter(vectors.values()))))
                return [m.id for m in sorted(movies, key=lambda m: (-cosine_similarity(vector, vectors[m.id]), m.id))]
            try:
                async with asyncio.timeout(90):
                    lexical, dense = await asyncio.gather(asyncio.to_thread(lexical_ranks, movies, query), vector_ranks())
                    # Reserve 24 semantic and 8 lexical candidates, capped at 32 unique IDs.
                    ids = list(dict.fromkeys(dense[:24] + lexical[:8]))
                    by_id = {m.id: m for m in movies}
                    passages = [{'id': mid, 'text': retrieval_text(by_id[mid])} for mid in ids]
                    if service.slot.locked():
                        raise DiscoveryError(409, 'Another AI request is running. Try again shortly.')
                    async with service.slot:
                        scores = await self.reranker.score(query, passages)
                expected = set(ids)
                if len(scores) != len(expected) or {mid for mid, _ in scores} != expected or any(not math.isfinite(score) or not 0 <= score <= 1 for _, score in scores):
                    raise ValueError('Reranker returned invalid candidates')
            except DiscoveryError:
                raise
            except TimeoutError:
                raise DiscoveryError(504, 'Search took too long. Please try again.') from None
            except Exception as error:
                logging.getLogger(__name__).warning('Relevance check failed: %s', type(error).__name__)
                raise DiscoveryError(503, 'Search relevance checking is unavailable. Please try again shortly.') from None
            ordered = sorted(scores, key=lambda pair: (-pair[1], ids.index(pair[0])))
            accepted = [mid for mid, score in ordered if score >= self.minimum_score]
            trace = {'version': CONFIG_VERSION, 'minimum_score': self.minimum_score, 'lexical_ids': lexical[:8], 'dense_ids': dense[:24], 'candidate_ids': ids, 'scores': [{'id': mid, 'score': score} for mid, score in ordered]}
            self.cache[key] = (monotonic() + 300, accepted, trace)
            while len(self.cache) > 64:
                self.cache.popitem(last=False)
            return accepted, trace
