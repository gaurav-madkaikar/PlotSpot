import asyncio
import pytest
from movie_companion.catalog import load_catalog
from movie_companion.catalog_import import collect_movies, record_ids


def test_provider_ids_are_validated_deduplicated_and_adult_included():
    assert record_ids([{'id':1,'adult':False},{'id':1,'adult':False},{'id':2,'adult':True}])==[1,2]
    for bad in [True,0,-1,'123',None]:
        with pytest.raises(ValueError):
            record_ids([{'id':bad}])


def test_importer_replaces_incomplete_metadata_and_keeps_ids_from_provider():
    class Provider:
        @staticmethod
        def _records(payload,key):
            return payload[key]
        async def _get(self,path,**params):
            if path=='/genre/movie/list':
                return {'genres':[{'id':10749},{'id':27}]}
            if path=='/configuration/languages':
                return []
            assert params['include_adult']=='true'
            return {'results':[{'id':1000+i+params['with_genres'],'adult':False} for i in range(20)]}
        async def movie(self,movie_id):
            return load_catalog()[0].model_copy(update={'id':movie_id,'source':'tmdb','overview':'' if movie_id==27205 else 'A valid synopsis.'})
    movies=asyncio.run(collect_movies(Provider(),10))
    assert len(movies)==len({m.id for m in movies})==10
    assert 27205 not in {m.id for m in movies}
    assert all(m.overview and len(m.cast)<=6 for m in movies)


def test_importer_resumes_saved_metadata_without_fetching_completed_movies(tmp_path):
    from movie_companion.tmdb_client import ProviderError
    checkpoint = tmp_path / 'metadata.json'
    class Provider:
        fail = True
        fetched = []
        @staticmethod
        def _records(payload, key):
            return payload[key]
        async def _get(self, path, **params):
            if path == '/genre/movie/list':
                return {'genres': [{'id': 1}]}
            if path == '/configuration/languages':
                return []
            return {'results': [{'id': 1000 + i + params['page'] * 20, 'adult': False} for i in range(20)]}
        async def movie(self, movie_id):
            self.fetched.append(movie_id)
            if self.fail and movie_id == 157336:
                raise ProviderError(404, 'Unavailable')
            return load_catalog()[0].model_copy(update={'id': movie_id, 'source': 'tmdb'})
    provider = Provider()
    first = asyncio.run(collect_movies(provider, 10, checkpoint=checkpoint))
    assert len(first) == 10
    completed = set(m.id for m in first)
    provider.fetched = []
    second = asyncio.run(collect_movies(provider, 10, checkpoint=checkpoint))
    assert [m.id for m in second] == [m.id for m in first]
    assert not set(provider.fetched) & completed


def test_large_catalog_discovers_more_pages_and_preserves_seed_ids():
    class Provider:
        pages = set()
        @staticmethod
        def _records(payload, key):
            return payload[key]
        async def _get(self, path, **params):
            if path == '/genre/movie/list':
                return {'genres': [{'id': i} for i in range(1, 20)]}
            if path == '/configuration/languages':
                return []
            self.pages.add(params['page'])
            return {'results': [{'id': 100000 + params['with_genres'] * 1000 + params['page'] * 20 + i} for i in range(20)]}
        async def movie(self, mid):
            return load_catalog()[0].model_copy(update={'id': mid, 'source': 'tmdb'})
    provider = Provider()
    movies = asyncio.run(collect_movies(provider, 1500, seed_ids=[9999]))
    assert len(movies) == len({m.id for m in movies}) == 1500
    assert 9999 in {m.id for m in movies} and max(provider.pages) >= 4
