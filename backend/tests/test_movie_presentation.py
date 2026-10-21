import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from movie_companion.catalog import load_catalog
from movie_companion.catalog_store import CatalogStore
from movie_companion.movie_details import load_movie_details
from movie_companion.movie_metadata import map_metadata
from movie_companion.movie_presentation import creative_credits, select_trailer
from movie_companion.schemas import MovieMetadata
from movie_companion.tmdb_client import TmdbClient, ProviderError


def video(**changes):
    return {'site':'YouTube','type':'Trailer','key':'YoHD9XEInc0','name':'Official trailer','official':True,'iso_639_1':'en',**changes}


def test_trailer_prefers_official_and_never_substitutes_teasers_or_clips():
    result = select_trailer({'results':[video(type='Teaser'),video(official=False,key='abcdefghijk'),video()]})
    assert result.youtube_key == 'YoHD9XEInc0' and result.official
    assert select_trailer({'results':[video(type='Clip')]}) is None
    assert select_trailer({'results':[video(official=False)]}).official is False


@pytest.mark.parametrize('payload',[None,{}, {'results':'bad'}, {'results':[None,False,video(key='https://evil.example/embed'),video(site='Vimeo'),video(official='true')]}, {'results':[video()]*501}])
def test_optional_invalid_media_is_ignored(payload):
    assert select_trailer(payload) is None


def test_roles_use_exact_jobs_and_preserve_screenplay_and_story_distinctions():
    result = creative_credits([
        {'name':'Nolan','job':'Screenplay'}, {'name':'Nolan','job':'Screenplay'},
        {'name':'Writer','job':'Story'}, {'name':'Zimmer','job':'Original Music Composer'},
        {'name':'Pfister','job':'Director of Photography'}, {'name':'Not the composer','job':'Music Editor'},
        {'name':'Not the cinematographer','job':'Camera Operator'}, {'name':'Unknown','job':['Writer']},
    ])
    assert [(c.name,c.role) for c in result] == [('Nolan','Screenplay'),('Writer','Story'),('Zimmer','Composer'),('Pfister','Cinematographer')]
    assert len(creative_credits([{'name':f'Writer {i}','job':'Writer'} for i in range(40)])) == 20


def test_optional_presentation_does_not_invalidate_core_movie_data():
    result = map_metadata({'budget':100,'videos':{'results':'invalid'}},[],[],presentation=True)
    assert result.budget == 100 and result.trailer is None and result.presentation_version == 1
    assert map_metadata({},[],[]).presentation_version is None


def test_old_detail_metadata_enriches_once_even_when_no_trailer_exists(tmp_path):
    path = tmp_path/'movies.db'
    store = CatalogStore(path)
    old = load_catalog()[0].model_copy(update={'source':'tmdb','detail_metadata':MovieMetadata(budget=100)})
    store.upsert_movie(old,fetched_at=datetime.now(timezone.utc).isoformat())
    class Provider:
        calls = 0
        async def movie(self,movie_id):
            self.calls += 1
            return old.model_copy(update={'detail_metadata':MovieMetadata(presentation_version=1,creative_credits=[{'name':'Writer','role':'Writer'}])})
    provider = Provider()
    first = asyncio.run(load_movie_details(old.id,store=store,provider=provider))
    second = asyncio.run(load_movie_details(old.id,store=CatalogStore(path),provider=provider))
    assert first == second and first.detail_metadata.budget == 100
    assert first.detail_metadata.trailer is None and provider.calls == 1


def test_presentation_upgrade_failure_keeps_existing_metadata(tmp_path):
    store = CatalogStore(tmp_path/'movies.db')
    old = load_catalog()[0].model_copy(update={'source':'tmdb','detail_metadata':MovieMetadata(budget=100)})
    store.upsert_movie(old,fetched_at=datetime.now(timezone.utc).isoformat())
    class Provider:
        async def movie(self,movie_id):
            raise ProviderError(503,'Unavailable')
    assert asyncio.run(load_movie_details(old.id,store=store,provider=Provider())) == old


def test_detail_request_maps_appended_video_and_creative_team_without_extra_video_call():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/languages'):
            return httpx.Response(200,json=[])
        assert request.url.params['append_to_response'] == 'credits,videos'
        return httpx.Response(200,json={'id':123,'title':'Example','release_date':'2024-01-01','runtime':100,'original_language':'en','genres':[],'credits':{'cast':[],'crew':[{'name':'Composer','job':'Original Music Composer'}]},'videos':{'results':[video()]}})
    async def scenario():
        async with httpx.AsyncClient(base_url='https://api.themoviedb.org/3',transport=httpx.MockTransport(handler)) as http:
            result = await TmdbClient(http).movie(123)
            assert result.detail_metadata.trailer.youtube_key == 'YoHD9XEInc0'
            assert result.detail_metadata.creative_credits[0].role == 'Composer'
    asyncio.run(scenario())
    assert len(paths) == 2 and not any(path.endswith('/videos') for path in paths)
