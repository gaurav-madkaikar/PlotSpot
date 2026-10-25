"""Vector comparison used by the upcoming semantic-search feature."""
import math

def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compare equal-length, nonempty finite vectors; zero vectors score 0."""
    len_left = len(left)
    len_right = len(right)
    if len_left == 0 or len_right == 0:
        raise ValueError("Vectors must be nonempty")
    if len_left != len_right:
        raise ValueError("Vectors must have equal length")
    if not all(math.isfinite(num) for num in left + right):
        raise ValueError("Vectors must have finite coordinates")
    norm_left = math.sqrt(sum(num**2 for num in left))
    norm_right = math.sqrt(sum(num**2 for num in right))
    dot_product = sum(l*r for l, r in zip(left, right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    result = dot_product / (norm_left * norm_right)
    return result