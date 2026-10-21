import asyncio
from datetime import datetime, timezone

import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.movie_metadata import map_metadata
from movie_companion.movie_details import load_movie_details
from movie_companion.schemas import MovieMetadata
from movie_companion.tmdb_client import ProviderError


def test_maps_metadata_roles_and_trusted_portraits():
    result = map_metadata({'release_date':'2010-07-16','budget':160000000,'revenue':839030630,
        'vote_average':8.4,'vote_count':30000,'spoken_languages':[{'english_name':'English','name':'English'}],
        'production_companies':[{'name':'Warner Bros.'}], 'production_countries':[{'name':'United States of America'}]},
        [{'name':'Leonardo DiCaprio','character':'Cobb','profile_path':'/actor.jpg'},
         {'name':'Another Actor','character':'','profile_path':'https://evil.example/a.jpg'}])
    assert result.release_date.isoformat() == '2010-07-16'
    assert result.budget == 160000000 and result.vote_average == 8.4
    assert result.spoken_languages == ['English']
    assert result.cast_credits[0].character == 'Cobb'
    assert result.cast_credits[0].profile_url == 'https://image.tmdb.org/t/p/w185/actor.jpg'
    assert result.cast_credits[1].profile_url is None and result.cast_credits[1].character is None


def test_unknown_money_and_unrated_movie_are_not_fabricated():
    result = map_metadata({'budget':0, 'revenue':0, 'vote_count':0, 'vote_average':0, 'release_date':'bad'}, [])
    assert result.budget is None and result.revenue is None and result.vote_average is None
    assert result.release_date is None and result.cast_credits == []


@pytest.mark.parametrize('payload', [{'vote_count':2,'vote_average':11}, {'budget':-1}, {'production_companies':[{'name':False}]}])
def test_invalid_upstream_metadata_is_rejected(payload):
    with pytest.raises(ValueError):
        map_metadata(payload, [])


def test_legacy_fresh_metadata_enriches_once_and_survives_restart(tmp_path):
    path = tmp_path/'movies.db'
    old = load_catalog()[0].model_copy(update={'source':'tmdb'})
    enriched = old.model_copy(update={'detail_metadata':MovieMetadata(presentation_version=1, budget=100, cast_credits=[{'name':'Actor','character':'Role'}])})
    store = CatalogStore(path)
    store.upsert_movie(old, fetched_at=datetime.now(timezone.utc).isoformat())
    class Provider:
        calls = 0
        async def movie(self, movie_id):
            self.calls += 1
            return enriched
    provider = Provider()
    assert asyncio.run(load_movie_details(old.id,store=store,provider=provider)).detail_metadata.budget == 100
    assert asyncio.run(load_movie_details(old.id,store=CatalogStore(path),provider=provider)).detail_metadata.budget == 100
    assert provider.calls == 1


def test_legacy_enrichment_failure_preserves_saved_movie(tmp_path):
    store = CatalogStore(tmp_path/'movies.db')
    old = load_catalog()[0].model_copy(update={'source':'tmdb'})
    store.upsert_movie(old, fetched_at=datetime.now(timezone.utc).isoformat())
    class Provider:
        async def movie(self, movie_id):
            raise ProviderError(503,'Unavailable')
    assert asyncio.run(load_movie_details(old.id,store=store,provider=Provider())) == old


def test_missing_optional_refresh_preserves_richer_metadata(tmp_path):
    store = CatalogStore(tmp_path/'movies.db')
    movie = load_catalog()[0].model_copy(update={'source':'tmdb','detail_metadata':MovieMetadata(budget=100,production_companies=['Studio'])})
    store.upsert_movie(movie,fetched_at='2000-01-01T00:00:00+00:00')
    store.upsert_movie(movie.model_copy(update={'detail_metadata':MovieMetadata(revenue=200)}),fetched_at=datetime.now(timezone.utc).isoformat())
    result = store.get_movie(movie.id).detail_metadata
    assert result.budget == 100 and result.revenue == 200 and result.production_companies == ['Studio']
