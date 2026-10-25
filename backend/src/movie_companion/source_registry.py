"""Human-reviewed source identities; neither browsers nor models choose URLs."""
import re
from .background_registry import ARTICLES

CALTECH_RECORD = 'awp8p-s4d82'
CALTECH_URL = f'https://authors.library.caltech.edu/records/{CALTECH_RECORD}'
SCRIPT_URL = 'https://imsdb.com/scripts/Interstellar.html'
SCRIPT_URLS = frozenset({
    SCRIPT_URL,
    'https://imsdb.com/scripts/Inception.html',
    'https://imsdb.com/scripts/Matrix,-The.html',
    'https://imsdb.com/scripts/Truman-Show,-The.html',
    'https://imsdb.com/scripts/Pulp-Fiction.html',
    'https://imsdb.com/scripts/Prestige,-The.html',
    'https://imsdb.com/scripts/Wall-E.html',
})
REVIEWED_LINKS = frozenset({CALTECH_URL, *SCRIPT_URLS, *(article.url for article in ARTICLES.values())})
WIKI_REVISION = re.compile(r'^https://en\.wikipedia\.org/w/index\.php\?oldid=[1-9][0-9]*$')


def valid_source_url(value: str) -> bool:
    if not isinstance(value,str):return False
    if bool(WIKI_REVISION.fullmatch(value)) or value in REVIEWED_LINKS:return True
    from .web_corpus_store import registered_url
    return registered_url(value)
