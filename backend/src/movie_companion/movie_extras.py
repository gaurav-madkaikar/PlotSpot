"""Bounded read-only TMDB watch options and recommendation summaries."""
from datetime import date, datetime
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator

IMAGE = r'^https://image\.tmdb\.org/t/p/w92/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$'
POSTER = r'^https://image\.tmdb\.org/t/p/w500/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$'


def image(path, size):
    return f'https://image.tmdb.org/t/p/{size}{path}' if isinstance(path,str) and re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)',path) else None


def valid_watch_link(link, movie_id, country):
    if not isinstance(link,str) or len(link)>1000:
        return False
    try:
        url=urlsplit(link)
    except ValueError:
        return False
    return (url.scheme=='https' and url.netloc=='www.themoviedb.org'
        and re.fullmatch(rf'/movie/{movie_id}(?:-[^/?#]+)?/watch',url.path) is not None
        and not url.fragment and url.query==f'locale={country}')


class WatchProvider(BaseModel):
    id: int = Field(strict=True,gt=0)
    name: str = Field(min_length=1,max_length=200)
    logo_url: str | None = Field(default=None,pattern=IMAGE)


class WatchGroup(BaseModel):
    kind: Literal['subscription','free','ads','rent','buy']
    providers: list[WatchProvider] = Field(max_length=40)


class WatchOptions(BaseModel):
    movie_id: int = Field(strict=True,gt=0)
    country: str = Field(pattern=r'^[A-Z]{2}$')
    status: Literal['available','unavailable','source_unavailable'] = 'source_unavailable'
    groups: list[WatchGroup] = Field(default_factory=list,max_length=5)
    watch_url: str | None = None
    checked_at: datetime | None = None
    stale: bool = False

    @model_validator(mode='after')
    def safe_link(self):
        if self.watch_url and not valid_watch_link(self.watch_url,self.movie_id,self.country):
            raise ValueError('Invalid watch link')
        return self


class WatchRegion(BaseModel):
    code: str = Field(pattern=r'^[A-Z]{2}$')
    name: str = Field(min_length=1,max_length=100)


class WatchRegions(BaseModel):
    items: list[WatchRegion] = Field(default_factory=list,max_length=300)
    checked_at: datetime | None = None
    stale: bool = False


class RelatedMovie(BaseModel):
    id: int = Field(strict=True,gt=0)
    title: str = Field(min_length=1,max_length=200)
    year: int | None = Field(default=None,ge=1888,le=2100)
    poster_url: str | None = Field(default=None,pattern=POSTER)
    adult: bool | None = Field(default=None,strict=True)
    vote_average: float | None = Field(default=None,strict=True,ge=0,le=10,allow_inf_nan=False)
    vote_count: int | None = Field(default=None,strict=True,ge=0)


class RelatedMovies(BaseModel):
    movie_id: int = Field(strict=True,gt=0)
    items: list[RelatedMovie] = Field(default_factory=list,max_length=6)
    checked_at: datetime | None = None
    stale: bool = False


def watch_options(payload,movie_id,country):
    if not isinstance(payload,dict) or type(payload.get('id')) is not int or payload['id'] != movie_id:
        raise ValueError('Mismatched watch identity')
    results=payload.get('results')
    if not isinstance(results,dict) or len(results)>300:
        raise ValueError('Invalid watch regions')
    region=results.get(country)
    if region is None:
        return WatchOptions(movie_id=movie_id,country=country,status='unavailable')
    if not isinstance(region,dict):
        raise ValueError('Invalid watch options')
    groups=[]
    for key,kind in [('flatrate','subscription'),('free','free'),('ads','ads'),('rent','rent'),('buy','buy')]:
        records=region.get(key,[])
        if not isinstance(records,list) or len(records)>100:
            raise ValueError('Invalid provider list')
        providers,seen=[],set()
        for record in records:
            if not isinstance(record,dict):
                raise ValueError('Invalid provider')
            provider=WatchProvider(id=record.get('provider_id'),name=record.get('provider_name'),logo_url=image(record.get('logo_path'),'w92'))
            if provider.id not in seen:
                providers.append(provider);seen.add(provider.id)
            if len(providers)==40:
                break
        if providers:
            groups.append(WatchGroup(kind=kind,providers=providers))
    link=region.get('link')
    return WatchOptions(movie_id=movie_id,country=country,status='available' if groups else 'unavailable',groups=groups,
        watch_url=link if valid_watch_link(link,movie_id,country) else None)


def watch_regions(payload):
    records=payload.get('results') if isinstance(payload,dict) else None
    if not isinstance(records,list) or len(records)>300:
        raise ValueError('Invalid region list')
    regions={}
    for record in records:
        if not isinstance(record,dict):
            raise ValueError('Invalid region')
        region=WatchRegion(code=record.get('iso_3166_1'),name=record.get('english_name'))
        regions[region.code]=region
    return WatchRegions(items=sorted(regions.values(),key=lambda r:r.name))


def related_movies(payload,movie_id):
    records=payload.get('results') if isinstance(payload,dict) else None
    if not isinstance(records,list) or len(records)>100:
        raise ValueError('Invalid recommendation list')
    movies,seen=[],{movie_id}
    for record in records:
        if not isinstance(record,dict):
            continue
        try:
            release=date.fromisoformat(record['release_date']) if record.get('release_date') else None
        except (ValueError,TypeError):
            release=None
        try:
            movie=RelatedMovie(id=record.get('id'),title=record.get('title'),year=release.year if release else None,
                poster_url=image(record.get('poster_path'),'w500'),adult=record.get('adult'),
                vote_average=record.get('vote_average'),vote_count=record.get('vote_count'))
        except ValueError:
            continue
        if movie.id not in seen:
            seen.add(movie.id);movies.append(movie)
        if len(movies)==6:
            break
    return RelatedMovies(movie_id=movie_id,items=movies)
