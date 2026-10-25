"""Select exact creative roles and safe trailer identifiers from optional TMDB data."""
import re

from .schemas import CreativeCredit, MovieTrailer

ROLES = {
    "Writer": "Writer", "Screenplay": "Screenplay", "Story": "Story",
    "Original Music Composer": "Composer", "Director of Photography": "Cinematographer",
}


def creative_credits(crew):
    if not isinstance(crew, list) or len(crew) > 10_000:
        return []
    credits, seen = [], set()
    for item in crew:
        if not isinstance(item, dict):
            continue
        job = item.get("job")
        role = ROLES.get(job) if isinstance(job, str) else None
        name = item.get("name")
        if not role or not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
            continue
        name = name.strip()
        if (role, name) not in seen:
            seen.add((role, name))
            credits.append(CreativeCredit(name=name, role=role))
        if len(credits) == 20:
            break
    return credits


def select_trailer(payload):
    if not isinstance(payload, dict):
        return None
    records = payload.get("results")
    if not isinstance(records, list) or len(records) > 500:
        return None
    eligible = []
    for item in records:
        if not isinstance(item, dict) or item.get("site") != "YouTube" or item.get("type") != "Trailer":
            continue
        key, name = item.get("key"), item.get("name")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
            continue
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
            continue
        official = item.get("official", False)
        if type(official) is not bool:
            continue
        trailer = MovieTrailer(name=name.strip(), youtube_key=key, official=official)
        eligible.append((not official, item.get("iso_639_1") != "en", key, trailer))
    return min(eligible, key=lambda entry: entry[:3])[3] if eligible else None
