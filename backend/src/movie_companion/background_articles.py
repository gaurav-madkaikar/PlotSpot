"""Bounded article ingestion and validated private snapshots; no page traversal."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .background_registry import ARTICLES, registry_fingerprint
from .evidence_store import SourceDocument
from .external_sources import ArticleSnapshot, read_bounded
from .source_sections import SourceSection

DEFAULT_CACHE = Path(__file__).resolve().parents[3] / '.cache/background-articles'
EXTRACTION = 'background-paragraphs-v1'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class ArticleHTML(HTMLParser):
    """Only visible paragraphs in the first article; metadata is never executed."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.article_depth = None
        self.article_done = False
        self.paragraph = None
        self.paragraphs = []
        self.visible = []
        self.jsonld = []
        self.ld = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if tag == 'script' and data.get('type') == 'application/ld+json':
            self.ld = []
        if tag == 'article' and self.article_depth is None and not self.article_done:
            self.article_depth = len(self.stack)
        if self.article_depth and tag == 'p' and not any(t in self.stack for t in ('script', 'style', 'nav', 'figure', 'aside')):
            if self.paragraph is not None:
                raise ValueError('Nested article paragraph')
            self.paragraph = []
        if tag == 'br' and self.paragraph is not None:
            self.paragraph.append(' ')

    def handle_data(self, data):
        if self.ld is not None:
            self.ld.append(data)
        if self.article_depth and not any(t in self.stack for t in ('script', 'style', 'nav', 'figure', 'aside')):
            self.visible.append(data)
            if self.paragraph is not None:
                self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.ld is not None:
            self.jsonld.append(''.join(self.ld))
            self.ld = None
        if tag == 'p' and self.paragraph is not None:
            text = ' '.join(''.join(self.paragraph).split())
            if text:
                self.paragraphs.append(text)
            self.paragraph = None
        if tag == 'article' and self.article_depth == len(self.stack):
            self.article_depth = None
            self.article_done = True
        if tag in self.stack:
            index = len(self.stack)-1-self.stack[::-1].index(tag)
            del self.stack[index:]


def _metadata(parser, record):
    entries = []
    for raw in parser.jsonld:
        if len(raw) > 100000:
            raise ValueError('Article metadata is too large')
        value = json.loads(raw)
        entries.extend(value if isinstance(value, list) else [value])
    entries = [e for e in entries if isinstance(e, dict) and e.get('@type') in ('Article', 'NewsArticle')]
    matches = []
    for entry in entries:
        identity = entry.get('mainEntityOfPage')
        identity = identity.get('@id') if isinstance(identity, dict) else identity
        if identity in (record.url, urlsplit(record.url).path):
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous reviewed article identity')
    data = matches[0]
    if data.get('headline') != record.headline:
        raise ValueError('Reviewed headline changed')
    published = data.get('datePublished')
    if not isinstance(published, str) or published[:10] != record.published_at:
        raise ValueError('Reviewed publication date changed')
    datetime.fromisoformat(published.replace('Z', '+00:00'))
    publisher = data.get('publisher')
    if not isinstance(publisher, dict) or str(publisher.get('name', '')).casefold() != record.publisher.casefold():
        raise ValueError('Wrong article publisher')
    authors = data.get('author', [])
    authors = authors if isinstance(authors, list) else [authors]
    names = [a.get('name', '') for a in authors if isinstance(a, dict)]
    # BFI identifies itself as JSON-LD author; the visible byline names the writer.
    visible = ' '.join(' '.join(parser.visible).split())
    if any(a not in names and a not in visible for a in record.authors):
        raise ValueError('Reviewed author is missing')


def parse_article(body, *, identifier, retrieved_at):
    if identifier not in ARTICLES or not isinstance(body, bytes) or not 20 <= len(body) <= 750000:
        raise ValueError('Unknown or oversized article')
    record = ARTICLES[identifier]
    parser = ArticleHTML()
    parser.feed(body.decode('utf-8', errors='strict'))
    parser.close()
    if not parser.article_done or parser.article_depth is not None:
        raise ValueError('Article body boundaries changed')
    _metadata(parser, record)
    selected, sections, text = [], [], ''
    for prefix, category in record.paragraphs:
        candidates = [p for p in parser.paragraphs if p.startswith(prefix)]
        if len(candidates) != 1 or not 20 <= len(candidates[0]) <= 4000:
            raise ValueError('Reviewed background paragraph changed or is ambiguous')
        selected.append((candidates[0], category))
    for index, (paragraph, category) in enumerate(selected):
        start = len(text)
        text += paragraph + ('\n\n' if index < len(selected)-1 else '')
        sections.append(SourceSection(start, len(text), f'Background {index+1}', category))
    digest = hashlib.sha256(body).hexdigest()
    # Revision identifies the extracted evidence, not volatile ads or page assets.
    identity = {'text': text, 'sections': [asdict(s) for s in sections],
                'registry': registry_fingerprint(identifier), 'extraction': EXTRACTION}
    revision = 'article-' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    source = SourceDocument(identifier, record.movie_id, text, record.publisher+' · '+record.headline,
                            record.url, revision, 'unknown', tuple(sections))
    datetime.fromisoformat(retrieved_at)
    return ArticleSnapshot(source, record.publisher, record.authors, record.published_at, retrieved_at, digest)


def _paths(identifier, cache_dir):
    if identifier not in ARTICLES:
        raise ValueError('Unknown reviewed article')
    root = Path(cache_dir)
    return root / (identifier+'.html'), root / (identifier+'.json')


def load_article(identifier, *, cache_dir=DEFAULT_CACHE):
    html, meta = _paths(identifier, cache_dir)
    if not html.is_file() or not meta.is_file() or html.stat().st_size > 750000 or meta.stat().st_size > 4000:
        raise ValueError('Reviewed article snapshot is missing or too large; refresh explicitly')
    data = json.loads(meta.read_text())
    if (not isinstance(data, dict) or data.get('extraction') != EXTRACTION
            or data.get('registry') != registry_fingerprint(identifier)):
        raise ValueError('Article registry or extraction changed; refresh explicitly')
    body = html.read_bytes()
    if data.get('content_sha256') != hashlib.sha256(body).hexdigest():
        raise ValueError('Article snapshot hash mismatch')
    snapshot = parse_article(body, identifier=identifier, retrieved_at=data.get('retrieved_at', ''))
    if data.get('revision') != snapshot.source.revision:
        raise ValueError('Article evidence revision mismatch')
    return snapshot


async def fetch_article(client, *, identifier):
    if identifier not in ARTICLES:
        raise ValueError('Unknown reviewed article')
    parts = urlsplit(ARTICLES[identifier].url)
    body = await read_bounded(client, path=parts.path, base_url=f'{parts.scheme}://{parts.netloc}',
                              maximum=750000, content_type='text/html')
    retrieved_at = datetime.now(timezone.utc).isoformat()
    return body, parse_article(body, identifier=identifier, retrieved_at=retrieved_at)


async def get_article(client, *, identifier, refresh=False, cache_dir=DEFAULT_CACHE):
    html, meta = _paths(identifier, cache_dir)
    if not refresh:
        return load_article(identifier, cache_dir=cache_dir), 'cached'
    body, snapshot = await fetch_article(client, identifier=identifier)
    html.parent.mkdir(parents=True, exist_ok=True)
    data = {'extraction': EXTRACTION, 'registry': registry_fingerprint(identifier),
            'content_sha256': snapshot.content_sha256, 'revision': snapshot.source.revision,
            'retrieved_at': snapshot.retrieved_at}
    # Metadata written last; a crash between files produces a detectable mismatch.
    for target, content in ((html, body), (meta, (json.dumps(data)+'\n').encode())):
        temporary = target.with_name(target.name+'.'+uuid4().hex+'.tmp')
        try:
            temporary.write_bytes(content)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return snapshot, 'refreshed'
