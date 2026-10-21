import pytest

from movie_companion.vector_math import cosine_similarity


@pytest.mark.parametrize("left, right, expected", [
    ([1.0, 2.0], [1.0, 2.0], 1.0),
    ([1.0, 2.0], [3.0, 6.0], 1.0),
    ([1.0, 0.0], [0.0, 1.0], 0.0),
    ([1.0, 0.0], [-1.0, 0.0], -1.0),
    ([1.0, 1.0], [1.0, 0.0], 2 ** -0.5),
    ([0.0, 0.0], [1.0, 2.0], 0.0),
    ([1.0, 2.0], [0.0, 0.0], 0.0),
])
def test_cosine_similarity(left, right, expected):
    assert cosine_similarity(left, right) == pytest.approx(expected)


@pytest.mark.parametrize("left, right", [
    ([], []),
    ([1.0], [1.0, 2.0]),
    ([float("nan")], [1.0]),
    ([1.0], [float("inf")]),
])
def test_rejects_invalid_vectors(left, right):
    with pytest.raises(ValueError):
        cosine_similarity(left, right)
