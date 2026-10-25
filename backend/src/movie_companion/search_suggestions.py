"""Bounded lexical suggestions from known movie records; no identity guessing."""

from collections import OrderedDict
from difflib import SequenceMatcher
from functools import lru_cache

from .catalog import load_catalog
from .schemas import Movie, SearchSuggestion, SuggestionResponse
from .search_text import normalize_search_text


class SuggestionIndex:
    def __init__(self, movies=(), *, capacity: int = 1500):
        self.capacity = capacity
        self.movies: OrderedDict[int, Movie] = OrderedDict()
        self._compiled = None
        self._generation = 0
        for movie in movies:
            self.remember(movie)

    def remember(self, movie: Movie) -> None:
        self._generation += 1
        self._compiled = None
        self.movies[movie.id] = movie
        self.movies.move_to_end(movie.id)
        while len(self.movies) > self.capacity:
            self.movies.popitem(last=False)

    def _labels(self):
        compiled = self._compiled
        if compiled is not None:
            return compiled
        generation = self._generation
        labels: dict[tuple[str, str], tuple[str, set[int]]] = {}
        # Suggestion requests can run in a worker thread while async hydration learns.
        snapshot = dict(self.movies)
        for movie in snapshot.values():
            for kind, label in [("movie", title) for title in [movie.title, *movie.alternative_titles[:8]]] + [("actor", name) for name in movie.cast[:12]] + [("director", name.strip()) for name in (movie.director or "").split(",")]:
                normalized = normalize_search_text(label)
                if not normalized:
                    continue
                key = (kind, normalized)
                if key not in labels:
                    labels[key] = (label, set())
                labels[key][1].add(movie.id)
        if generation == self._generation:
            self._compiled = (snapshot, labels)
        return snapshot, labels

    def suggest(self, query: str, *, threshold: float = 0.8) -> SuggestionResponse:
        needle = normalize_search_text(query)
        snapshot, labels = self._labels()
        response = SuggestionResponse(items=[], indexed_movies=len(snapshot))
        # Short fragments are ambiguous; exact known queries need no correction.
        if len(needle) < 4 or any(needle == normalized for _, normalized in labels):
            return response
        # A real title/name completion is more useful than a similarly spelled unrelated word.
        completions = {key: value for key, value in labels.items() if key[1].startswith(needle)
                       and 2 * len(needle) / (len(needle) + len(key[1])) >= threshold}
        candidates = completions or labels
        ranked = []
        for (kind, normalized), (label, movie_ids) in candidates.items():
            matcher = SequenceMatcher(None, needle, normalized, autojunk=False)
            # Both estimates are upper bounds: rejected candidates cannot pass ratio().
            if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                continue
            score = matcher.ratio()
            if score >= threshold:
                display = snapshot[next(iter(movie_ids))].title if kind == "movie" and len(movie_ids) == 1 else label
                ranked.append(SearchSuggestion(label=display, kind=kind,
                                               movie_ids=sorted(movie_ids), score=score))
        ranked.sort(key=lambda item: (-item.score, item.kind, item.label.casefold()))
        unique = {}
        for item in ranked:
            unique.setdefault((item.kind, item.label, tuple(item.movie_ids)), item)
        response.items = list(unique.values())[:3]
        return response


@lru_cache(maxsize=1)
def get_suggestion_index() -> SuggestionIndex:
    return SuggestionIndex(load_catalog())
