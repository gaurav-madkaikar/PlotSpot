import pytest

from movie_companion.search_text import normalize_search_text


@pytest.mark.parametrize("text, expected", [
    ("  AMY   ADAMS  ", "amy adams"),
    ("Spider-Man: No Way Home", "spider man no way home"),
    ("Dune\t2021\n", "dune 2021"),
    ("  기생충  ", "기생충"),
    (" --- ", ""),
])
def test_normalizes_search_text(text, expected):
    assert normalize_search_text(text) == expected
