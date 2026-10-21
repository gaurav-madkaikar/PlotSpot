"""Translate optional detail fields without inventing missing values."""
import re
from datetime import date

from .schemas import CastCredit, MovieMetadata
from .movie_presentation import creative_credits, select_trailer


def map_metadata(details, cast, crew=None, *, presentation=False):
    def names(key, field='name'):
        records = details.get(key) or []
        if not isinstance(records, list) or len(records) > 100 or not all(isinstance(r, dict) for r in records):
            raise ValueError('Invalid detail metadata')
        values = [r.get(field) or r.get('name') for r in records]
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError('Invalid metadata names')
        return list(dict.fromkeys(v.strip() for v in values))

    release = details.get('release_date')
    try:
        release = date.fromisoformat(release) if release else None
    except (ValueError, TypeError):
        release = None
    credits = []
    for item in cast[:12]:
        profile = item.get('profile_path')
        url = f'https://image.tmdb.org/t/p/w185{profile}' if isinstance(profile, str) and re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', profile) else None
        character = item.get('character') or None
        credits.append(CastCredit(name=item['name'], character=character, profile_url=url))
    return MovieMetadata(
        release_date=release,
        spoken_languages=names('spoken_languages', 'english_name'),
        production_companies=names('production_companies'),
        production_countries=names('production_countries'),
        # TMDB zero budgets/revenues mean unreported; they are not free productions.
        budget=details.get('budget') or None, revenue=details.get('revenue') or None,
        vote_average=details.get('vote_average') if details.get('vote_count') else None,
        vote_count=details.get('vote_count'), status=details.get('status') or None,
        original_title=details.get('original_title') or None, cast_credits=credits,
        creative_credits=creative_credits(crew),
        trailer=select_trailer(details.get('videos')) if presentation else None,
        presentation_version=1 if presentation else None,
    )
