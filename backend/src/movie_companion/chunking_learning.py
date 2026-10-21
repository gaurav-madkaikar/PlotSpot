"""Character-window teaching baseline; not the final token-aware article chunker."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    start: int
    end: int
    text: str


def split_windows(text: str, *, max_chars: int, overlap_chars: int) -> list[TextChunk]:
    """Learner slice: window → record → stop at end or advance with overlap.

    The wrapper supplies valid nonblank text and settings. Preserve source
    offsets, including whitespace; end is exclusive as in Python slicing.
    """
    if not text.strip():
        raise ValueError("Text must not be blank")
    chunks = []
    for i in range(0, len(text), max_chars - overlap_chars):
        start = i
        end = min(i + max_chars, len(text))
        chunks.append(TextChunk(start=start, end=end, text=text[start:end]))
        if end == len(text):
            break
    return chunks

def chunk_text(text: str, *, max_chars: int = 600, overlap_chars: int = 100) -> list[TextChunk]:
    """Assistant-owned bounds and source-span consistency checks."""
    if not isinstance(text, str) or len(text) > 100000:
        raise ValueError("Source text must be a string of at most 100000 characters")
    if type(max_chars) is not int or not 1 <= max_chars <= 2000:
        raise ValueError("max_chars must be an integer from 1 to 2000")
    if type(overlap_chars) is not int or not 0 <= overlap_chars < max_chars:
        raise ValueError("overlap_chars must be an integer from zero to max_chars - 1")
    if not text.strip():
        return []
    chunks = split_windows(text, max_chars=max_chars, overlap_chars=overlap_chars)
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Nonblank text requires chunks")
    previous = None
    for chunk in chunks:
        if not isinstance(chunk, TextChunk) or type(chunk.start) is not int or type(chunk.end) is not int:
            raise ValueError("Chunks must have integer source offsets")
        if not 0 <= chunk.start < chunk.end <= len(text):
            raise ValueError("Invalid chunk span")
        if chunk.end - chunk.start > max_chars or chunk.text != text[chunk.start:chunk.end]:
            raise ValueError("Chunk must match its bounded source span")
        if previous is None:
            if chunk.start != 0:
                raise ValueError("First chunk must start at source beginning")
        elif previous.end == len(text) or chunk.start != previous.end - overlap_chars:
            raise ValueError("Chunks must advance with the requested overlap")
        if chunk.end < len(text) and chunk.end - chunk.start != max_chars:
            raise ValueError("Only the final chunk can be shorter than max_chars")
        previous = chunk
    if chunks[-1].end != len(text):
        raise ValueError("Chunks must cover the source end")
    return chunks
