"""Inspect overlapping chunks of authored fictional production notes."""

from movie_companion.chunking_learning import chunk_text


ARTICLE = (
    "Orbit Day is a fictional film used in this learning project. "
    "Its sound team recorded a washing machine and slowed the hum to create spacecraft ambience. "
    "The costume team used recycled fabric and painted the suits silver. "
    "The production programme describes these techniques but contains no box-office revenue data."
)


if __name__ == "__main__":
    print("FICTIONAL TEACHING DATA — not real movie reporting")
    for number, chunk in enumerate(chunk_text(ARTICLE, max_chars=100, overlap_chars=20), start=1):
        print(f"Chunk {number}: [{chunk.start}:{chunk.end}] {chunk.text!r}")
