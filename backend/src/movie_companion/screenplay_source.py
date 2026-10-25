"""Reviewed IMSDb screenplays, private snapshots, and scene-preserving documents.

Script text is untrusted evidence, never an instruction or released-film authority.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from .evidence_store import SourceDocument
from .external_sources import read_bounded
from .preparation_jobs import atomic_json
from .source_sections import SourceSection

PARSER_VERSION = 'imsdb-scenes-v1'
MAX_BYTES = 1_000_000
MAX_TEXT = 500_000
SCENE_HEADING = re.compile(r'^(?:\d+[A-Z]?\s+)?(?:INT\./EXT\.|EXT\./INT\.|INT/EXT\.|I/E\.|INT\.|EXT\.)\s+\S')


@dataclass(frozen=True)
class ScriptMapping:
    title: str
    path: str
    header_title: str
    author: str
    version_marker: str
    version_label: str


SCRIPTS = {
    27205: ScriptMapping('Inception', '/scripts/Inception.html', 'INCEPTION',
                         'Christopher Nolan', 'SHOOTING SCRIPT', 'Shooting script; released-film match unverified'),
    603: ScriptMapping('The Matrix', '/scripts/Matrix,-The.html', 'THE MATRIX',
                       'Larry and Andy Wachowski', 'April 8, 1996', '1996-04-08 draft; released-film match unverified'),
    157336: ScriptMapping('Interstellar', '/scripts/Interstellar.html', 'INTERSTELLAR',
                          'Jonathan Nolan', 'MARCH 12 2008', '2008-03-12 early draft; released-film match unverified'),
    37165: ScriptMapping('The Truman Show', '/scripts/Truman-Show,-The.html',
                         '"The Truman Show", early, by Andrew M. Niccol',
                         'Andrew M. Niccol', 'A Screen Play',
                         'Early screenplay; released-film match unverified'),
    680: ScriptMapping('Pulp Fiction', '/scripts/Pulp-Fiction.html',
                       '"PULP FICTION" -- by Quentin Tarantino & Roger Avary',
                       'Quentin Tarantino & Roger Avary', 'PULP [pulp] n.',
                       'Undated screenplay; released-film match unverified'),
    1124: ScriptMapping('The Prestige', '/scripts/Prestige,-The.html', 'THE PRESTIGE',
                        'Jonathan Nolan & Christopher Nolan', 'Written by',
                        'Undated screenplay; released-film match unverified'),
    10681: ScriptMapping('WALL-E', '/scripts/Wall-E.html', 'WALL-E',
                         'Andrew Stanton & Pete Docter', 'Written by',
                         'Undated screenplay; released-film match unverified'),
}


def script_mapping(movie_id):
    if type(movie_id) is not int or movie_id not in SCRIPTS:
        raise ValueError('Movie has no reviewed screenplay mapping')
    return SCRIPTS[movie_id]


class _ScreenplayHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.done = False
        self.pre_depth = 0
        self.hidden = 0
        self.parts = []
        self.size = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'pre' and not self.done:
            self.pre_depth += 1
            if self.pre_depth > 2:
                raise ValueError('Screenplay container nesting exceeds the reviewed format')
            self.active = True
        if self.active and tag in ('script', 'style'):
            self.hidden += 1
        if self.active and not self.hidden and tag == 'br':
            self.handle_data('\n')

    def handle_endtag(self, tag):
        if self.active and tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        if tag == 'pre' and self.active:
            self.pre_depth -= 1
            if self.pre_depth == 0:
                self.active, self.done = False, True

    def handle_data(self, text):
        if self.active and not self.hidden:
            self.size += len(text)
            if self.size > MAX_TEXT:
                raise ValueError('Screenplay text exceeds the budget')
            self.parts.append(text)


def normalize_script(text):
    # Keep line and dialogue boundaries; remove layout indentation and repeated blank lines.
    lines = [re.sub(r'[\t \xa0]+', ' ', line).strip()
             for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def validate_header(text, mapping):
    header = text[:2000]
    if not text.splitlines() or text.splitlines()[0] != mapping.header_title:
        raise ValueError('Screenplay title does not match the reviewed movie')
    if mapping.author not in header or mapping.version_marker not in header:
        raise ValueError('Screenplay author/version changed; review required')


def scene_sections(text):
    headings = [(m.start(), m.group().strip()) for m in re.finditer(r'^.*$', text, re.MULTILINE)
                if SCENE_HEADING.match(m.group())]
    if not headings or len(headings) > 1000:
        raise ValueError('Screenplay needs a bounded set of recognizable scenes')
    boundaries = [(0, 'Opening and title material'), *headings]
    sections = []
    for index, (start, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        if end > start:
            sections.append(SourceSection(start, end, heading[:200], 'plot'))
    return tuple(sections)


@dataclass(frozen=True)
class ScriptSnapshot:
    movie_id: int
    text: str
    source_ref: str
    retrieved_at: str
    body_sha256: str
    text_sha256: str
    parser_version: str = PARSER_VERSION

    def __post_init__(self):
        mapping = script_mapping(self.movie_id)
        if self.source_ref != 'https://imsdb.com' + mapping.path or self.parser_version != PARSER_VERSION:
            raise ValueError('Invalid script provenance or parser revision')
        if not isinstance(self.text, str) or not 100 <= len(self.text) <= MAX_TEXT:
            raise ValueError('Invalid screenplay text length')
        if self.text != normalize_script(self.text):
            raise ValueError('Screenplay is not canonically normalized')
        validate_header(self.text, mapping)
        for digest in (self.body_sha256, self.text_sha256):
            if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
                raise ValueError('Invalid screenplay fingerprint')
        if hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError('Screenplay cache text fingerprint mismatch')
        try:
            timestamp = datetime.fromisoformat(self.retrieved_at)
        except (ValueError, TypeError):
            raise ValueError('Invalid retrieval timestamp') from None
        if timestamp.tzinfo is None:
            raise ValueError('Retrieval timestamp needs a timezone')
        scene_sections(self.text)

    @property
    def revision(self):
        return PARSER_VERSION + '-' + self.text_sha256

    @property
    def eligible_for_quiz(self):
        return False


def parse_script(body: bytes, *, movie_id: int, retrieved_at: str) -> ScriptSnapshot:
    mapping = script_mapping(movie_id)
    if not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BYTES:
        raise ValueError('Invalid screenplay HTML size')
    try:
        html = body.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        # Reviewed IMSDb pages also contain Windows-1252 screenplay characters.
        html = body.decode('cp1252', errors='strict')
    parser = _ScreenplayHTML()
    parser.feed(html)
    parser.close()
    if not parser.done:
        raise ValueError('Missing or incomplete screenplay container')
    text = normalize_script(''.join(parser.parts))
    validate_header(text, mapping)
    return ScriptSnapshot(movie_id, text, 'https://imsdb.com' + mapping.path, retrieved_at,
                          hashlib.sha256(body).hexdigest(), hashlib.sha256(text.encode()).hexdigest())


async def load_script(client, *, movie_id: int, cache_root: Path, refresh: bool = False):
    """Return (validated snapshot, cached/fetched); explicit refresh re-reads the source."""
    mapping = script_mapping(movie_id)
    if type(refresh) is not bool:
        raise ValueError('Refresh must be a boolean')
    path = cache_root / f'{movie_id}.json'
    if path.exists() and not refresh:
        if path.stat().st_size > 3_000_000:
            raise ValueError('Screenplay cache exceeds the budget')
        snapshot = ScriptSnapshot(**json.loads(path.read_text()))
        if snapshot.movie_id != movie_id:
            raise ValueError('Wrong cached movie')
        return snapshot, 'cached'
    body = await read_bounded(client, path=mapping.path, base_url='https://imsdb.com',
                              maximum=MAX_BYTES, content_type='text/html')
    snapshot = parse_script(body, movie_id=movie_id, retrieved_at=datetime.now(timezone.utc).isoformat())
    atomic_json(path, asdict(snapshot))
    return snapshot, 'fetched'


def script_documents(snapshot: ScriptSnapshot):
    """Group whole scenes into bounded documents; chunks never cross a scene.

    Return document plus its global start offset, allowing exact attribution.
    """
    groups = []
    current = []
    for scene in scene_sections(snapshot.text):
        if scene.end - scene.start > 80_000:
            raise ValueError('Individual screenplay scene exceeds the document budget')
        if current and (scene.end - current[0].start > 80_000 or len(current) >= 150):
            groups.append(current)
            current = []
        current.append(scene)
    groups.append(current)
    result = []
    for index, group in enumerate(groups):
        start, end = group[0].start, group[-1].end
        sections = tuple(SourceSection(s.start-start, s.end-start, s.title, 'plot') for s in group)
        document = SourceDocument(f'imsdb-{snapshot.movie_id}-part-{index}', snapshot.movie_id,
                                  snapshot.text[start:end], 'IMSDb · ' + SCRIPTS[snapshot.movie_id].title,
                                  snapshot.source_ref, snapshot.revision, 'spoiler', sections)
        result.append((document, start))
    return result
