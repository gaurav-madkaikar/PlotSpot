import pytest

import movie_companion.chunking_learning as chunking
from movie_companion.chunking_learning import TextChunk, chunk_text


def test_short_source_is_one_chunk_with_original_whitespace():
    assert chunk_text(" hi ", max_chars=8, overlap_chars=2) == [TextChunk(0, 4, " hi ")]


def test_overlap_windows_cover_source_and_stop_at_end():
    assert chunk_text("ABCDEFGHIJK", max_chars=5, overlap_chars=2) == [
        TextChunk(0, 5, "ABCDE"), TextChunk(3, 8, "DEFGH"), TextChunk(6, 11, "GHIJK"),
    ]


def test_no_overlap_exact_boundary_has_no_extra_chunk():
    assert chunk_text("abcdef", max_chars=3, overlap_chars=0) == [
        TextChunk(0, 3, "abc"), TextChunk(3, 6, "def"),
    ]


def test_final_short_chunk_keeps_remaining_text():
    assert chunk_text("abcdefgh", max_chars=5, overlap_chars=1) == [
        TextChunk(0, 5, "abcde"), TextChunk(4, 8, "efgh"),
    ]


def test_unicode_offsets_use_python_characters_not_bytes():
    assert chunk_text("A🎬BéC", max_chars=3, overlap_chars=1) == [
        TextChunk(0, 3, "A🎬B"), TextChunk(2, 5, "BéC"),
    ]


def test_blank_source_bypasses_splitter(monkeypatch):
    def must_not_split(*args, **kwargs):
        pytest.fail("Blank text should bypass splitting")
    monkeypatch.setattr(chunking, "split_windows", must_not_split)
    assert chunk_text("") == []
    assert chunk_text(" \n\t ") == []


@pytest.mark.parametrize("settings", [
    {"max_chars": 0}, {"max_chars": 2001}, {"max_chars": True},
    {"overlap_chars": -1}, {"max_chars": 4, "overlap_chars": 4}, {"overlap_chars": True},
])
def test_invalid_settings_rejected(settings):
    with pytest.raises(ValueError):
        chunk_text("article", **settings)


@pytest.mark.parametrize("text", [None, "x" * 100001])
def test_invalid_source_rejected(text):
    with pytest.raises(ValueError):
        chunk_text(text)


@pytest.mark.parametrize("chunks", [
    [], [TextChunk(1, 3, "bc")], [TextChunk(0, 3, "wrong")],
    [TextChunk(0, 3, "abc")],
    [TextChunk(0, 3, "abc"), TextChunk(3, 6, "def")],
])
def test_invalid_output_rejected(monkeypatch, chunks):
    monkeypatch.setattr(chunking, "split_windows", lambda *args, **kwargs: chunks)
    with pytest.raises(ValueError):
        chunk_text("abcdef", max_chars=3, overlap_chars=1)
