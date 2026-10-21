"""In-memory source offsets attached only after complete snapshot validation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PassageLocation:
    source_key: str
    movie_id: int
    source_label: str
    spoiler_status: str
    text: str
    start: int
    end: int
    section_start: int
    section_end: int
    section_title: str
    section_category: str
