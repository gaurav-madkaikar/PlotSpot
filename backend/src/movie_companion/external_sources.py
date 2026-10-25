"""Bounded read-only adapters for explicit reviewed records. No model-driven browsing."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re

import httpx

from .evidence_store import SourceDocument
from .source_registry import CALTECH_RECORD, CALTECH_URL, SCRIPT_URL
from .source_sections import SourceSection

CALTECH_TITLE = "Building Interstellar's black hole: the gravitational renderer"


async def read_bounded(client, *, path, base_url, maximum, content_type):
    if client.base_url != httpx.URL(base_url) or client.follow_redirects:
        raise ValueError('Use the reviewed HTTPS host with redirects disabled')
    async with client.stream('GET', path) as response:
        response.raise_for_status()
        if content_type not in response.headers.get('content-type', '').lower():
            raise ValueError('Unexpected source content type')
        content = bytearray()
        async for part in response.aiter_bytes():
            content.extend(part)
            if len(content) > maximum:
                raise ValueError('Source exceeds the bounded read limit')
        return bytes(content)


@dataclass(frozen=True)
class ArticleSnapshot:
    source: SourceDocument
    publisher: str
    authors: tuple[str, ...]
    published_at: str
    retrieved_at: str
    content_sha256: str


def map_caltech_record(data, *, content_sha256, retrieved_at):
    if not isinstance(data, dict) or data.get('id') != CALTECH_RECORD:
        raise ValueError('Wrong Caltech record identity')
    metadata = data.get('metadata')
    if not isinstance(metadata, dict) or metadata.get('title') != CALTECH_TITLE:
        raise ValueError('Wrong reviewed movie article title')
    text = metadata.get('description')
    if not isinstance(text, str) or not 20 <= len(text) <= 10000 or 'Interstellar' not in text:
        raise ValueError('Missing bounded movie abstract')
    # This adapter handles the reviewed plain-text abstract, not arbitrary HTML.
    if '<' in text or '>' in text:
        raise ValueError('Unexpected abstract markup')
    publisher, date, creators = metadata.get('publisher'), metadata.get('publication_date'), metadata.get('creators')
    if not isinstance(publisher, str) or not 1 <= len(publisher) <= 100:
        raise ValueError('Missing publisher')
    if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?', date):
        raise ValueError('Missing publication date')
    if not isinstance(creators, list) or not 1 <= len(creators) <= 20:
        raise ValueError('Missing authors')
    if any(not isinstance(c, dict) or not isinstance(c.get('person_or_org'), dict) for c in creators):
        raise ValueError('Invalid author records')
    authors = tuple(c['person_or_org'].get('name') for c in creators)
    if len(authors) != len(creators) or any(not isinstance(a, str) or not 1 <= len(a) <= 100 for a in authors):
        raise ValueError('Invalid authors')
    source = SourceDocument('caltech-dngr', 157336, text, 'CaltechAUTHORS · ' + CALTECH_TITLE, CALTECH_URL,
                            'caltech-' + content_sha256, 'unknown', (SourceSection(0, len(text), 'Visual effects', 'effects'),))
    return ArticleSnapshot(source, publisher, authors, date, retrieved_at, content_sha256)


async def fetch_caltech_article(client, *, movie_id):
    if type(movie_id) is not int or movie_id != 157336:
        raise ValueError('Movie has no reviewed external article')
    body = await read_bounded(client, path=f'/api/records/{CALTECH_RECORD}', base_url='https://authors.library.caltech.edu', maximum=200000, content_type='application/json')
    return map_caltech_record(json.loads(body), content_sha256=hashlib.sha256(body).hexdigest(), retrieved_at=datetime.now(timezone.utc).isoformat())


class _ScriptHeader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_pre = False
        self.done = False
        self.parts = []
        self.size = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'pre' and not self.done:
            self.in_pre = True

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre, self.done = False, True

    def handle_data(self, data):
        if self.in_pre and self.size < 2000:
            part = data[:2000 - self.size]
            self.parts.append(part)
            self.size += len(part)


@dataclass(frozen=True)
class ScriptProvenance:
    movie_id: int
    title: str
    source_ref: str
    draft_date: str
    retrieved_at: str
    content_sha256: str

    @property
    def eligible_for_quiz(self):
        # This registry contains only an early draft; no released-film verification.
        return False


def inspect_script(body, *, retrieved_at):
    parser = _ScriptHeader()
    parser.feed(body.decode('utf-8', errors='strict'))
    parser.close()
    header = '\n'.join(parser.parts)
    lines = [line.strip() for line in header.splitlines() if line.strip()]
    if not lines or lines[0] != 'INTERSTELLAR':
        raise ValueError('Screenplay title does not match reviewed movie')
    if not re.search(r'\bMARCH\s+12\s+2008\b', header):
        raise ValueError('Screenplay version changed; manual review required')
    return ScriptProvenance(157336, 'Interstellar', SCRIPT_URL, '2008-03-12', retrieved_at, hashlib.sha256(body).hexdigest())


async def fetch_script_provenance(client, *, movie_id):
    if type(movie_id) is not int or movie_id != 157336:
        raise ValueError('Movie has no reviewed screenplay mapping')
    body = await read_bounded(client, path='/scripts/Interstellar.html', base_url='https://imsdb.com', maximum=1000000, content_type='text/html')
    return inspect_script(body, retrieved_at=datetime.now(timezone.utc).isoformat())
