import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from movie_companion.catalog import load_catalog
from movie_companion.legacy_semantic_catalog_search import CatalogQuery, search_catalog
from movie_companion.main import app
from movie_companion.schemas import Movie
from movie_companion.search_intent import interpret
from movie_companion.semantic_catalog import save_index, read_index
from movie_companion.semantic_search import SemanticSearch


def run(coro):
    return asyncio.run(coro)


def fail_request(request):
    pytest.fail('Identity/genre/empty routes must not call AI')


def service_for(tmp_path, handler=fail_request):
    movies = list(load_catalog())
    path = tmp_path/'catalog.json'
    save_index(movies,[[1,0] for _ in movies],path)
    return SemanticSearch(httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url='http://local'),path=path)


@pytest.mark.parametrize('query,ids,kind',[
    ('Interstellar',[157336],'title_cast'),('Amy Adams',[329865],'title_cast'),
    ('Movies starring Amy Adams',[329865],'title_cast'),('Intersteler',[157336],'typo'),
    ('romance',[],'genre'),('romantic comedy',[],'genre'),
    ('documentary',[],'genre'),('pasta recipes and knitting',[],'semantic'),
    ('Science Fiction',[27205,157336,329865,603,438631],'genre'),
])
def test_routing_and_empty_states_make_no_model_calls(tmp_path,query,ids,kind):
    service=service_for(tmp_path)
    result=run(search_catalog(service,CatalogQuery(query=query)))
    assert [m.id for m in result.items]==ids
    assert result.match_type==kind
    assert result.total==len(ids)
    assert result.total_pages==(1 if ids else 0)


def test_title_matching_does_not_override_explicit_runtime_filter(tmp_path):
    service=service_for(tmp_path)
    for query in ['Interstellar','Intersteler']:
        result=run(search_catalog(service,CatalogQuery(query=query,max_runtime=120)))
        assert result.items==[]
    assert run(search_catalog(service,CatalogQuery(query='romance',genre='Horror'))).items==[]


def test_genre_negation_and_word_boundaries():
    intent=interpret('a comedy without romance')
    assert intent.required=={'Comedy'} and intent.excluded=={'Romance'} and intent.genre_only
    assert not interpret('an award winning story').required
    assert interpret('a sci-fi story about communication').required=={'Science Fiction'}
    assert interpret('a family struggling with money').required==set()


def test_supported_description_is_embedded_and_ranked_only_within_constraints(tmp_path):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'embeddings':[[1,0]]})
    service=service_for(tmp_path,handler)
    result=run(search_catalog(service,CatalogQuery(query='sci-fi about communication',max_runtime=120)))
    assert [m.id for m in result.items]==[329865]
    assert len(calls)==1


def test_identity_title_containing_genre_word_takes_precedence(tmp_path):
    movie=load_catalog()[0].model_copy(update={'title':'War of Dreams'})
    path=tmp_path/'index.json'
    save_index([movie],[[1,0]],path)
    service=SemanticSearch(httpx.AsyncClient(transport=httpx.MockTransport(fail_request)),path=path)
    result=run(search_catalog(service,CatalogQuery(query='War of Dreams')))
    assert [m.id for m in result.items]==[27205]


def test_pages_are_complete_unique_and_do_not_embed_browsing(tmp_path):
    service=service_for(tmp_path)
    pages=[run(search_catalog(service,CatalogQuery(page=p,page_size=3))) for p in range(1,5)]
    assert [len(p.items) for p in pages]==[3,3,3,1]
    ids=[m.id for page in pages for m in page.items]
    assert len(set(ids))==len(ids)==10
    assert all(p.total==10 and p.total_pages==4 for p in pages)
    outside=run(search_catalog(service,CatalogQuery(page=5,page_size=3)))
    assert outside.items==[] and outside.total==10


def test_imported_manifest_supports_more_than_ten_validated_tmdb_records(tmp_path):
    movies=[m.model_copy(update={'source':'tmdb'}) for m in load_catalog()]
    movies.append(Movie(id=597,title='Titanic',year=1997,runtime_minutes=194,language='English',genres=['Romance','Drama'],director='James Cameron',cast=['Kate Winslet'],overview='Two passengers fall in love aboard a ship.',tagline='',source='tmdb',artwork_kind='placeholder'))
    path=tmp_path/'catalog.json'
    saved=save_index(movies,[[1,0] for _ in movies],path,source_movie_ids=[m.id for m in movies])
    service=SemanticSearch(httpx.AsyncClient(transport=httpx.MockTransport(fail_request)),path=path)
    result=run(search_catalog(service,CatalogQuery(query='romance')))
    assert [m.title for m in result.items]==['Titanic']
    assert result.indexed_movies==11
    assert result.applied_genres==['Romance']
    with pytest.raises(ValueError):
        save_index(movies, saved.vectors,path,source_movie_ids=[597])
    assert len(read_index(path).movies)==11


@pytest.mark.parametrize('params',[{'page':0},{'page_size':41},{'q':'x'*301},{'page':10001}])
def test_endpoint_pagination_bounds(params):
    assert TestClient(app).get('/api/search/catalog',params={'unified':'true',**params}).status_code==422




def superhero_service(tmp_path):
    base = list(load_catalog())
    # Existing reviewed IDs keep this fixture independent of an external catalog.
    movies = [
        base[0].model_copy(update={'title': 'The Dark Knight', 'overview': 'Batman fights a criminal mastermind in Gotham.', 'genres': ['Action', 'Crime'], 'runtime_minutes': 152}),
        base[1].model_copy(update={'title': 'Spider-Man: Across the Spider-Verse', 'overview': 'Miles travels through the multiverse to protect his friends.', 'genres': ['Action', 'Animation'], 'runtime_minutes': 140}),
        base[2].model_copy(update={'title': 'A War Hero', 'overview': 'A soldier becomes a hero after rescuing his companions.', 'genres': ['War'], 'runtime_minutes': 110}),
        base[3].model_copy(update={'title': 'The Final Stand', 'overview': 'The Avengers reunite to defend the world.', 'genres': ['Action'], 'runtime_minutes': 120}),
        base[4].model_copy(update={'title': 'Spider Horror', 'overview': 'A giant spider terrorizes a village.', 'genres': ['Horror'], 'runtime_minutes': 90}),
    ]
    path = tmp_path / 'superheroes.json'
    save_index(movies, [[1, 0] for _ in movies], path)
    def handler(request):
        return httpx.Response(200, json={'embeddings': [[1, 0]]})
    return SemanticSearch(httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://local'), path=path), movies


@pytest.mark.parametrize('query', ['hero movies', 'superhero movies', 'superheroes', 'super hero films', 'heroes'])
def test_superhero_queries_use_specific_title_and_synopsis_evidence(tmp_path, query):
    service, movies = superhero_service(tmp_path)
    result = run(search_catalog(service, CatalogQuery(query=query)))
    assert {m.id for m in result.items} == {movies[i].id for i in [0, 1, 3]}
    assert result.total == 3


def test_superhero_theme_keeps_filters_pagination_and_descriptive_constraints(tmp_path):
    service, movies = superhero_service(tmp_path)
    result = run(search_catalog(service, CatalogQuery(query='hero movies', max_runtime=140, page_size=1, page=2)))
    assert result.total == 2 and result.total_pages == 2
    assert len(result.items) == 1
    assert result.items[0].runtime_minutes <= 140
    result = run(search_catalog(service, CatalogQuery(query='animated superhero movies')))
    assert [m.id for m in result.items] == [movies[1].id]
    result = run(search_catalog(service, CatalogQuery(query='superhero movies about knitting')))
    assert result.items == []


def test_superhero_negation_and_canonical_title_precedence(tmp_path):
    service, movies = superhero_service(tmp_path)
    result = run(search_catalog(service, CatalogQuery(query='movies without superheroes')))
    assert {m.id for m in result.items} == {movies[2].id, movies[4].id}
    result = run(search_catalog(service, CatalogQuery(query='A War Hero')))
    assert [m.id for m in result.items] == [movies[2].id]
    assert result.match_type == 'title_cast'
    assert not interpret('heroic movies').required_themes
