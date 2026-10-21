"""Bounded discovery of public sources already cited by a movie article."""
import re
from urllib.parse import urlsplit,urlunsplit

import httpx

from .public_web import SourceRejected, public_url
from .web_search import SearchHit, SearchUnavailable
from .wikipedia_source import MOVIE_ARTICLES

POLICY='wikipedia-cited-source-discovery-v1'
BACKGROUND=re.compile(r'(behind|production|filming|cinematograph|effects|interview|sound|score|costume|casting|set|making|featurette|stunt)',re.I)
STORY=re.compile(r'(plot|story|ending|explain|analysis|review|character|narrative)',re.I)
BLOCKED=('wikipedia.org','wikimedia.org','imdb.com','rottentomatoes.com','youtube.com','youtu.be',
         'facebook.com','instagram.com','twitter.com','x.com','tiktok.com','reddit.com','amazon.com')


def candidate_url(value):
    if not isinstance(value,str):raise SourceRejected('Invalid cited URL')
    parts=urlsplit(value)
    if parts.scheme=='http':
        value=urlunsplit(('https',parts.netloc,parts.path,parts.query,''))
    url=public_url(value);host=(urlsplit(url).hostname or '').removeprefix('www.')
    if any(host==domain or host.endswith('.'+domain) for domain in BLOCKED):
        raise SourceRejected('Excluded cited source family')
    if re.search(r'\.(?:pdf|jpg|jpeg|png|gif|zip|mp3|mp4)(?:$|\?)',url,re.I):
        raise SourceRejected('Unsupported cited asset')
    return url


def rank(url,purpose,movie):
    text=url.casefold();title='-'.join(re.findall(r'\w+',movie.title.casefold()))
    signal=BACKGROUND if purpose=='background' else STORY
    score=12 if signal.search(text) else 0
    if title and (title in text or title.replace('-','') in re.sub(r'\W','',text)):score+=6
    if str(movie.year or '') in text:score+=2
    if urlsplit(url).path.count('/')>1:score+=1
    return score


class WikipediaReferenceSearch:
    def __init__(self,client):
        if (client.base_url!=httpx.URL('https://en.wikipedia.org') or client.follow_redirects):
            raise ValueError('Use the fixed Wikipedia client without redirects')
        self.client=client;self.provider=POLICY

    async def search(self,movie,purpose,*,limit=15):
        if purpose not in ('story','background') or type(limit)is not int or not 1<=limit<=30:
            raise ValueError('Invalid cited-source discovery request')
        title=MOVIE_ARTICLES.get(movie.movie_id)
        if not title:raise SearchUnavailable('Movie article unavailable')
        try:
            response=await self.client.get('/w/api.php',params={'action':'query','prop':'extlinks',
                'titles':title,'ellimit':'max','redirects':'1','format':'json'})
            response.raise_for_status()
            if len(response.content)>600000:raise SearchUnavailable('Wikipedia reference response too large')
            payload=response.json();pages=payload['query']['pages']
            rows=next(iter(pages.values())).get('extlinks',[])
        except (ValueError,KeyError,TypeError,httpx.HTTPError) as error:
            raise SearchUnavailable('Wikipedia cited sources unavailable') from error
        found=[];seen=set()
        for row in rows:
            try:url=candidate_url(row.get('*'))
            except (SourceRejected,AttributeError):continue
            if url in seen:continue
            seen.add(url);found.append((rank(url,purpose,movie),url))
        found.sort(key=lambda pair:(-pair[0],pair[1]))
        if not found:raise SearchUnavailable('No eligible Wikipedia cited sources')
        return [SearchHit(urlsplit(url).hostname or 'Cited source',url,'Wikipedia citation discovery only',index+1)
                for index,(_,url) in enumerate(found[:limit])]
