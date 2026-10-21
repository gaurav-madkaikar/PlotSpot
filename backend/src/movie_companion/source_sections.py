"""Section provenance and routing; headings are not a spoiler-safety classifier."""
from dataclasses import dataclass
from typing import Literal

from .chunking_learning import TextChunk, chunk_text

Category = Literal['plot', 'production', 'casting', 'filming', 'music', 'effects', 'other']
CATEGORIES = {'plot', 'production', 'casting', 'filming', 'music', 'effects', 'other'}
BACKGROUND = {'production', 'casting', 'filming', 'music', 'effects'}


@dataclass(frozen=True)
class SourceSection:
    start: int
    end: int
    title: str
    category: Category

    def __post_init__(self):
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start < self.end:
            raise ValueError('Section must have a positive character span')
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 200:
            raise ValueError('Invalid section heading')
        if self.category not in CATEGORIES:
            raise ValueError('Invalid section category')


def heading_category(title: str) -> Category:
    """Conservative explicit heading mapping; unknown children inherit their parent."""
    heading = title.casefold().strip()
    return {
        'plot': 'plot', 'synopsis': 'plot', 'plot summary': 'plot',
        'production': 'production', 'development': 'production',
        'writing': 'production', 'pre-production': 'production',
        'casting': 'casting', 'cast': 'casting',
        'filming': 'filming', 'principal photography': 'filming',
        'music': 'music', 'soundtrack': 'music', 'score': 'music',
        'visual effects': 'effects', 'special effects': 'effects', 'effects': 'effects',
    }.get(heading, 'other')


def source_chunks(source, *, max_chars=600, overlap_chars=100) -> list[TextChunk]:
    """Use learner windows within each validated section; offsets stay document-relative."""
    if not source.sections:
        return chunk_text(source.text, max_chars=max_chars, overlap_chars=overlap_chars)
    chunks = []
    for section in source.sections:
        for chunk in chunk_text(source.text[section.start:section.end], max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(TextChunk(section.start + chunk.start, section.start + chunk.end, chunk.text))
    return chunks


def section_for_chunk(source, chunk: TextChunk) -> SourceSection | None:
    if not source.sections:
        return None
    for section in source.sections:
        if section.start <= chunk.start < chunk.end <= section.end:
            return section
    raise ValueError('Evidence chunk crosses section boundaries')


def matches_purpose(category: str, purpose: str) -> bool:
    if purpose == 'story':
        return category == 'plot'
    if purpose == 'background':
        return category in BACKGROUND
    raise ValueError('Unknown evidence purpose')


def routed_chunks(source, *, purpose: str, max_chars=600, overlap_chars=100):
    # Fail closed for old/unclassified sources during new content preparation.
    return [chunk for chunk in source_chunks(source, max_chars=max_chars, overlap_chars=overlap_chars)
            if (section := section_for_chunk(source, chunk)) is not None
            and matches_purpose(section.category, purpose)]
