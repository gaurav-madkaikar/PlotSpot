"""Read-only source inspection; article text is untrusted and spoiler-unclassified."""

from html.parser import HTMLParser
import re

import httpx

from .evidence_store import SourceDocument
from .source_sections import SourceSection, heading_category


MOVIE_ARTICLES = {
    27205: "Inception",
    157336: "Interstellar (film)",
    329865: "Arrival (film)",
    603: "The Matrix",
    546554: "Knives Out",
    496243: "Parasite (2019 film)",
    129: "Spirited Away",
    37165: "The Truman Show",
    120467: "The Grand Budapest Hotel",
    438631: "Dune (2021 film)",
    155: "The Dark Knight",
}
from .source_coverage import ADDITIONAL_MOVIES
MOVIE_ARTICLES.update(ADDITIONAL_MOVIES)


async def request_article(client: httpx.AsyncClient, *, title: str) -> httpx.Response:
    """Learner slice: GET /w/api.php with action=parse, page, prop=text|revid,
    format=json, formatversion=2, disableeditsection=1, disabletoc=1.

    Return the response; the wrapper handles status, JSON and source validation.
    Use the supplied client and params dictionary, not a manually assembled URL.
    """
    response = await client.get(
        "/w/api.php",
        params={
            "action": "parse",
            "page": title,
            "prop": "text|revid",
            "format": "json",
            "formatversion": 2,
            "disableeditsection": 1,
            "disabletoc": 1,
        },
    )
    response.raise_for_status()
    return response


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buffer, self.blocks = [], []
        self.ignored = 0
        self.heading = None
        self.heading_parts = []
        self.parents = []
        self.title, self.category = "Introduction", "other"
        self.section_number = 0

    def flush(self):
        line = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
        if line:
            self.blocks.append((self.section_number, self.title, self.category, line))
        self.buffer.clear()

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored += 1
        if self.ignored:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush()
            self.heading, self.heading_parts = int(tag[1]), []
        elif self.heading is None and tag in {"p", "br", "li", "tr"}:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if self.heading is not None and tag == f"h{self.heading}":
            title = re.sub(r"\s+", " ", "".join(self.heading_parts)).strip()
            self.parents = [(level, category) for level, category in self.parents if level < self.heading]
            category = heading_category(title)
            if category == "other" and self.parents:
                category = self.parents[-1][1]
            self.parents.append((self.heading, category))
            self.title, self.category = title or "Untitled", category
            self.section_number += 1
            self.heading = None
            self.buffer.append(title)
            self.flush()
        elif self.heading is None and tag in {"p", "li", "tr"}:
            self.flush()

    def handle_data(self, data):
        if not self.ignored:
            (self.heading_parts if self.heading is not None else self.buffer).append(data)

    def document(self):
        self.flush()
        text, sections = "", []
        previous = None
        for number, title, category, line in self.blocks:
            if text:
                text += "\n\n"
            if number != previous:
                if sections:
                    old = sections[-1]
                    sections[-1] = SourceSection(old.start, len(text), old.title, old.category)
                sections.append(SourceSection(len(text), len(text) + len(line), title, category))
            text += line
            old = sections[-1]
            sections[-1] = SourceSection(old.start, len(text), old.title, old.category)
            previous = number
        return text, tuple(sections)


def map_article_response(data: object, *, movie_id: int, expected_title: str) -> SourceDocument:
    if not isinstance(data, dict) or "error" in data:
        raise ValueError("Wikipedia returned an invalid or error response")
    page = data.get("parse")
    if not isinstance(page, dict):
        raise ValueError("Wikipedia parse record is missing")
    title, html, page_id, revision = page.get("title"), page.get("text"), page.get("pageid"), page.get("revid")
    if not isinstance(title, str) or title.replace("_", " ").casefold() != expected_title.casefold():
        raise ValueError("Returned article does not match the reviewed movie mapping")
    if type(page_id) is not int or page_id <= 0 or type(revision) is not int or revision <= 0:
        raise ValueError("Source page and revision IDs are required")
    if not isinstance(html, str) or not html.strip() or len(html) > 2000000:
        raise ValueError("Expected bounded article HTML")
    parser = _PlainText()
    parser.feed(html)
    parser.close()
    # This extraction representation is versioned; offsets will refer to it.
    text, sections = parser.document()
    # Reference lists/navigation are not movie evidence. Stop at their heading,
    # rather than raising storage limits or silently cutting a paragraph.
    stop = next((index for index, section in enumerate(sections)
                 if section.title.casefold() in {"references", "notes", "external links", "further reading"}), len(sections))
    sections = sections[:stop]
    text = text[:sections[-1].end] if sections else ""
    return SourceDocument(
        source_id=f"enwiki-{page_id}", movie_id=movie_id, text=text,
        source_label=f"English Wikipedia contributors: {title}",
        source_ref=f"https://en.wikipedia.org/w/index.php?oldid={revision}",
        revision=f"enwiki-{revision}-sections-v3-body", spoiler_status="unknown", sections=sections,
    )


async def fetch_movie_source(client: httpx.AsyncClient, *, movie_id: int) -> SourceDocument:
    if type(movie_id) is not int or movie_id not in MOVIE_ARTICLES:
        raise ValueError("Movie has no reviewed Wikipedia mapping yet")
    if client.base_url != httpx.URL("https://en.wikipedia.org") or client.follow_redirects:
        raise ValueError("Use the fixed Wikipedia HTTPS client with redirects disabled")
    title = MOVIE_ARTICLES[movie_id]
    response = await request_article(client, title=title)
    response.raise_for_status()
    if len(response.content) > 2000000:
        raise ValueError("Wikipedia response exceeds the teaching size limit")
    return map_article_response(response.json(), movie_id=movie_id, expected_title=title)
