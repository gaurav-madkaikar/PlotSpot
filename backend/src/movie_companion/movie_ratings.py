"""TMDB scores shared by full records and lightweight title previews."""

def movie_rating(movie):
    source = movie.detail_metadata if movie.detail_metadata is not None else movie
    score, votes = source.vote_average, source.vote_count
    return (score, votes) if score is not None and votes is not None and votes > 0 else (None, 0)


# Fixed policy rather than a baseline that changes with a filter or catalog page.
RATING_POLICY = 'trusted-rating-v1-reference-7-weight-500'
REFERENCE_SCORE = 7.0
REFERENCE_VOTES = 500


def trusted_rating(movie):
    score, votes = movie_rating(movie)
    if score is None:
        return None
    # This bounded form avoids multiplying a potentially large vote count by a float.
    return REFERENCE_SCORE + (score - REFERENCE_SCORE) * (votes / (votes + REFERENCE_VOTES))


def rating_sort_key(movie, sort_by='trusted'):
    score, votes = movie_rating(movie)
    if sort_by not in ('trusted', 'rating'):
        raise ValueError('Unsupported rating order')
    order = trusted_rating(movie) if sort_by == 'trusted' else score
    # Both modes keep missing scores last and have deterministic reported-score ties.
    return (score is None, -(order or 0), -(score or 0), -votes)
