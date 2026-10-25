import asyncio

import httpx

from movie_companion.movie_web_sources import MovieIdentity
from movie_companion.wikipedia_references import WikipediaReferenceSearch, candidate_url
from movie_companion.public_web import SourceRejected


MOVIE=MovieIdentity(27205,'Inception',2010,'Christopher Nolan')


def test_cited_http_links_are_upgraded_and_unsafe_families_are_excluded():
    assert candidate_url('http://theasc.com/inception/behind-the-scenes')=='https://theasc.com/inception/behind-the-scenes'
    for url in ('https://www.imdb.com/title/tt1375666/','https://youtube.com/watch?v=x','file:///etc/passwd'):
        try:candidate_url(url)
        except SourceRejected:pass
        else:raise AssertionError('Excluded citation was accepted')


def test_background_reference_discovery_is_bounded_and_ranked():
    payload={'query':{'pages':{'1':{'extlinks':[
        {'*':'http://example.org/inception-review'},
        {'*':'https://theasc.com/inception/cinematography-behind-the-scenes'},
        {'*':'https://youtube.com/watch?v=ignored'},
        {'*':'https://example.net/inception-ending-analysis'},
    ]}}}}
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))
    async def run():
        async with httpx.AsyncClient(base_url='https://en.wikipedia.org',follow_redirects=False,
                transport=transport) as client:
            hits=await WikipediaReferenceSearch(client).search(MOVIE,'background',limit=2)
            assert len(hits)==2
            assert hits[0].url=='https://theasc.com/inception/cinematography-behind-the-scenes'
            assert all(hit.snippet=='Wikipedia citation discovery only' for hit in hits)
    asyncio.run(run())


def test_reference_candidate_budget_is_capped_at_thirty():
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'query':{'pages':{'1':{'extlinks':[]}}}}))
    async def run():
        async with httpx.AsyncClient(base_url='https://en.wikipedia.org',follow_redirects=False,
                transport=transport) as client:
            try:await WikipediaReferenceSearch(client).search(MOVIE,'story',limit=31)
            except ValueError:pass
            else:raise AssertionError('Unbounded reference request was accepted')
    asyncio.run(run())
