"""Conservative genre and theme cues supported by saved movie metadata."""
import re
from dataclasses import dataclass
from .search_text import normalize_search_text

GENRE_ALIASES = {
    'romance': 'Romance', 'romantic': 'Romance', 'rom com': 'Romance',
    'science fiction': 'Science Fiction', 'sci fi': 'Science Fiction', 'scifi': 'Science Fiction',
    'horror': 'Horror', 'comedy': 'Comedy', 'comedies': 'Comedy',
    'thriller': 'Thriller', 'thrillers': 'Thriller', 'mystery': 'Mystery',
    'documentary': 'Documentary', 'documentaries': 'Documentary',
    'animated': 'Animation', 'animation': 'Animation', 'fantasy': 'Fantasy',
    'action': 'Action', 'adventure': 'Adventure', 'western': 'Western',
    'family friendly': 'Family', 'tv movie': 'TV Movie',
    'war': 'War', 'music': 'Music', 'musical': 'Music', 'history': 'History', 'historical': 'History',
    'drama': 'Drama', 'crime': 'Crime',
}
# Specific character/franchise phrases provide evidence where a synopsis omits
# "superhero". Match whole phrases, not generic words such as power or hero.
SUPERHERO_EVIDENCE = re.compile(
    r'\b(?:superhero(?:es)?|super hero(?:es)?|superhuman|superpowers?|super powers|'
    r'batman|spider man|spider verse|superman|avengers|iron man|captain america|'
    r'wonder woman|black panther|deadpool|x men|wolverine|hulk|'
    r'justice league|fantastic four|guardians of the galaxy)\b'
)
SUPERHERO_QUERY = re.compile(r'\b(?:superheroes|superhero|super heroes|super hero|heroes|hero)\b')

STOP_WORDS = set('a an the and or with about of in on to for that who is are it as from by movies movie film films story stories want looking find me something watch thoughtful good great fun interesting please like but very some involving'.split())
SYNONYMS = {
    'communication': {'communicate', 'language', 'linguist'},
    'communicating': {'communicate', 'language', 'linguist'},
    'hacker': {'programmer', 'computer'}, 'simulation': {'simulated', 'computer'},
    'inequality': {'economic', 'wealthy', 'poor'}, 'spirits': {'spirit'},
    'dysfunctional': {'family'}, 'family': {'family', 'children', 'father', 'daughter'},
    'father': {'father', 'daughter', 'children'}, 'children': {'child', 'daughter', 'son'},
    'aliens': {'alien', 'extraterrestrial'}, 'alien': {'alien', 'extraterrestrial'},
}


@dataclass(frozen=True)
class SearchIntent:
    required: frozenset[str]
    excluded: frozenset[str]
    genre_only: bool
    terms: frozenset[str]
    required_themes: frozenset[str] = frozenset()
    excluded_themes: frozenset[str] = frozenset()


def stem(word: str) -> str:
    # Small English normalization, not a general-purpose multilingual stemmer.
    if len(word) > 5 and word.endswith('ing'):
        word = word[:-3]
    elif len(word) > 4 and word.endswith('s'):
        word = word[:-1]
    return word[:-1] if len(word) > 5 and word.endswith('e') else word


def interpret(query: str) -> SearchIntent:
    normalized = normalize_search_text(query)
    required, excluded = set(), set()
    remaining = normalized
    required_themes, excluded_themes = set(), set()
    for match in SUPERHERO_QUERY.finditer(normalized):
        prefix = normalized[:match.start()].split()
        negative = any(w in {'no', 'not', 'without', 'avoid', 'excluding'} for w in prefix[-2:])
        (excluded_themes if negative else required_themes).add('superhero')
    remaining = SUPERHERO_QUERY.sub(' ', remaining)
    # Long phrases first; word boundaries avoid recognizing "war" in "award".
    for alias, genre in sorted(GENRE_ALIASES.items(), key=lambda item: -len(item[0])):
        pattern = r'\b' + re.escape(alias) + r'\b'
        for match in re.finditer(pattern, normalized):
            prefix = normalized[:match.start()].split()
            negative = any(w in {'no', 'not', 'without', 'avoid', 'excluding'} for w in prefix[-2:])
            (excluded if negative else required).add(genre)
        remaining = re.sub(pattern, ' ', remaining)
    if re.search(r'\brom com\b', normalized):
        required.add('Comedy')
    if normalized in {'family', 'family movies', 'family films'}:
        required.add('Family')
        remaining = ''
    words = set(remaining.split()) - STOP_WORDS - {'no', 'not', 'without', 'avoid', 'excluding'}
    expanded = set(words)
    for word in words:
        expanded.update(SYNONYMS.get(word, ()))
    return SearchIntent(frozenset(required), frozenset(excluded), bool(required or excluded) and not words and not (required_themes or excluded_themes), frozenset(stem(w) for w in expanded if len(w) >= 3), frozenset(required_themes), frozenset(excluded_themes))


def synopsis_support(overview: str, intent: SearchIntent) -> int:
    words = {stem(w) for w in normalize_search_text(overview).split()} - STOP_WORDS
    return len(words & intent.terms)


def theme_support(title: str, overview: str, intent: SearchIntent) -> bool:
    """Evidence-backed theme constraint independent of descriptive term overlap."""
    superhero = bool(SUPERHERO_EVIDENCE.search(normalize_search_text(title + ' ' + overview)))
    present = {'superhero'} if superhero else set()
    return intent.required_themes <= present and not intent.excluded_themes & present
