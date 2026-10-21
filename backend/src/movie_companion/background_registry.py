"""Reviewed background article identities and paragraph scope, never model URLs."""
from dataclasses import dataclass
import hashlib
import json
from dataclasses import asdict


@dataclass(frozen=True)
class BackgroundArticle:
    id: str
    movie_id: int
    url: str
    headline: str
    publisher: str
    authors: tuple[str, ...]
    published_at: str
    kind: str
    # Prefixes identify complete, manually inspected background paragraphs.
    paragraphs: tuple[tuple[str, str], ...]
    query: str


ARTICLES = {
    'time-arrival': BackgroundArticle(
        'time-arrival', 329865,
        'https://time.com/4677598/arrival-oscar-cinematography/',
        'Inside the Cinematography of the Oscar-Nominated Movie Arrival',
        'TIME', ('Olivier Laurent',), '2017-02-22', 'interview',
        (("That’s where Patrice Vermette, the film’s production designer, comes in.", 'production'),
         ('The cavernous chamber was born out of that experience.', 'filming'),
         ('Outside of the spaceship, Young was inspired by the work of photographer', 'filming')),
        'Practical spacecraft chamber built physical set instead of green screens; '
        'photographer Martina Hoogland Ivanow Speedway inspired cinematography; James Turrell light art.'),
    'bfi-arrival': BackgroundArticle(
        'bfi-arrival', 329865,
        'https://www.bfi.org.uk/features/strange-new-worlds-craft-denis-villeneuve',
        'Strange new worlds: the craft of Denis Villeneuve',
        'BFI', ('Nikki Baughan',), '2021-09-22', 'article',
        (('Composer Jóhannsson eschews the traditional overarching emotional music', 'music'),),
        'Arrival score human voices harmonies throat singing blended with sound design.'),
}


def registry_fingerprint(identifier):
    return hashlib.sha256(json.dumps(asdict(ARTICLES[identifier]), sort_keys=True).encode()).hexdigest()


def articles_for_movie(movie_id):
    if type(movie_id) is not int or movie_id <= 0:
        raise ValueError('A positive movie ID is required')
    records = [a for a in ARTICLES.values() if a.movie_id == movie_id]
    if not 1 <= len(records) <= 2:
        raise ValueError('Movie needs one or two reviewed background articles')
    return records
