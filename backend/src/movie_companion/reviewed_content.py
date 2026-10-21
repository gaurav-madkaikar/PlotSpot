"""Bind authored movie content to an explicitly reviewed article revision.

Markers locate supporting evidence; they do not automatically prove a claim.
The wording and distractors in the banks require human review.
"""
import hashlib
import json
from pathlib import Path
import re

from .movie_facts import MovieFact, MovieFacts
from .movie_questions import QuestionCitation
from .movie_quiz import MovieQuiz, QuizItem
from .source_registry import valid_source_url
from .source_sections import matches_purpose
from .wikipedia_source import MOVIE_ARTICLES

BANK_PATH = Path(__file__).with_name("content_banks")
SUPPORTED_MOVIES = frozenset({157336, 27205, 329865, 603, 546554, 37165, 496243, 129, 120467, 438631, 155})
CONTENT_VERSION = "reviewed-multi-movie-v2"


def _sentence_boundaries(text):
    """Keep common honorifics and initials inside their complete sentence."""
    boundaries = [0]
    for match in re.finditer(r'[.!?](?:\[[^\]\n]+\])*(?::\s*[0-9–-]+)?\s+(?=[A-Z“"])', text):
        if text[match.start()] == '.':
            word = re.search(r'\b([A-Za-z]+)$', text[:match.start()])
            if word and (word[1].casefold() in {'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'sr', 'jr'}
                         or re.fullmatch(r'[A-Z]', word[1])):
                continue
        boundaries.append(match.end())
    return [*boundaries, len(text)]


def load_bank(movie_id):
    if type(movie_id) is not int or movie_id not in SUPPORTED_MOVIES - {157336}:
        raise ValueError("No reviewed content bank for this movie")
    return json.loads((BANK_PATH / f"{movie_id}.json").read_text())


def compile_reviewed_collection(source):
    bank = load_bank(source.movie_id)
    expected = f"English Wikipedia contributors: {MOVIE_ARTICLES[source.movie_id]}"
    match = re.fullmatch(r"enwiki-([1-9][0-9]*)-sections-v3-body", source.revision)
    if (not source.sections or source.source_label != expected or not match
            or not valid_source_url(source.source_ref)
            or source.source_ref != f"https://en.wikipedia.org/w/index.php?oldid={match[1]}"):
        raise ValueError("Expected the reviewed movie article with section-aware revision provenance")

    def citation(entry, purpose):
        markers = entry["evidence_markers"]
        if not markers or any(not isinstance(m, str) or not m.strip() for m in markers):
            raise ValueError("Evidence markers are required")
        for section in source.sections:
            if not matches_purpose(section.category, purpose):
                continue
            # Select complete sentences rather than quote a truncated window.
            body = source.text[section.start:section.end]
            for paragraph in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", body):
                text = paragraph.group().strip()
                if not all(m.casefold() in text.casefold() for m in markers):
                    continue
                boundaries = _sentence_boundaries(text)
                spans = [(a, b) for a in boundaries for b in boundaries
                         if 20 <= b - a <= 600 and all(m.casefold() in text[a:b].casefold() for m in markers)]
                if not spans:
                    continue
                start, end = min(spans, key=lambda span: (span[1] - span[0], span[0]))
                identity = f"{source.movie_id}:{source.source_id}:{source.revision}:{section.start + paragraph.start() + start}:{end-start}"
                return [QuestionCitation(
                    passage_id=hashlib.sha256(identity.encode()).hexdigest()[:32],
                    source_label=source.source_label, source_ref=source.source_ref,
                    revision=source.revision, excerpt=text[start:end].strip(),
                )]
        raise ValueError(f"Missing {purpose} evidence for {entry['id']}")

    quiz = MovieQuiz(status="ready", message="Saved story quiz.", can_generate_more=False, items=[
        QuizItem(id=e["id"], question=e["question"], kind=e.get("kind", "plot"),
                 options=e["options"], correct_index=e["correct_index"],
                 explanation=e["explanation"], citations=citation(e, "story"))
        for e in bank["quiz"]
    ])
    facts = MovieFacts(status="ready", message="Saved production background.", items=[
        MovieFact(id=e["id"], title=e["title"], text=e["text"], citations=citation(e, "background"))
        for e in bank["facts"]
    ])
    from .content_store import ContentStore
    ContentStore.validate(quiz, facts)
    return quiz, facts
