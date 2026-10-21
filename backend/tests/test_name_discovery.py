import asyncio

import httpx
import pytest

from movie_companion.name_discovery import acting_movie_ids, director_movie_ids
from movie_companion.tmdb_client import ProviderError, TmdbClient


def run(handler, check):
    async def work():
        async with httpx.AsyncClient(base_url="https://api.themoviedb.org/3", transport=httpx.MockTransport(handler)) as http:
            await check(TmdbClient(http))
    asyncio.run(work())


def test_title_and_person_pages_keep_identities_and_page_parameters():
    requests = []
    def handler(request):
        requests.append(request)
        item = {"id": 123, "title": "Film", "adult": False} if request.url.path.endswith("/movie") else {"id": 456, "name": "Director", "known_for_department": "Directing"}
        return httpx.Response(200, json={"page": 2, "total_pages": 3, "results": [item, item]})
    async def check(provider):
        titles = await provider.search_movie_names(" Film ", page=2)
        people = await provider.search_person_names("Director", page=2)
        assert [item.id for item in titles.items] == [123]
        assert [item.id for item in people.items] == [456]
        assert titles.page == 2 and titles.total_pages == 3
        assert all(r.url.params["page"] == "2" and r.url.params["include_adult"] == "true" for r in requests)
        assert requests[0].url.params["query"] == "Film"
    run(handler, check)


def test_same_name_people_remain_distinct_and_adult_classification_is_retained():
    def handler(request):
        return httpx.Response(200, json={"page": 1, "total_pages": 1, "results": [{"id": 1, "name": "Alex Lee"}, {"id": 2, "name": "Alex Lee"}, {"id": 3, "name": "Adult", "adult": True}]})
    async def check(provider):
        assert [p.id for p in (await provider.search_person_names("Alex Lee")).items] == [1, 2, 3]
    run(handler, check)


@pytest.mark.parametrize("item", [{"id": True, "title": "Film"}, {"id": 0, "title": "Film"}, {"id": 1, "title": "Film", "adult": "false"}])
def test_invalid_identity_is_sanitized(item):
    def handler(request):
        return httpx.Response(200, json={"page": 1, "total_pages": 1, "results": [item]})
    async def check(provider):
        with pytest.raises(ProviderError) as error:
            await provider.search_movie_names("Film")
        assert error.value.status == 502
    run(handler, check)


def test_person_credits_validate_identity_and_keep_roles_separate():
    def handler(request):
        assert request.url.path == "/3/person/456/movie_credits"
        return httpx.Response(200, json={"id": 456, "cast": [{"id": 1}, {"id": 1}], "crew": [{"id": 2, "job": "Director"}, {"id": 3, "job": "Producer"}]})
    async def check(provider):
        credits = await provider.person_movie_credits(456)
        assert acting_movie_ids(credits["cast"]) == [1]
        assert [r["job"] for r in credits["crew"]] == ["Director", "Producer"]
    run(handler, check)


def test_mismatched_person_credits_are_rejected():
    def handler(request):
        return httpx.Response(200, json={"id": 999, "cast": [], "crew": []})
    async def check(provider):
        with pytest.raises(ProviderError, match="mismatched"):
            await provider.person_movie_credits(456)
    run(handler, check)


def test_invalid_inputs_never_call_network():
    def handler(request):
        raise AssertionError("No network expected")
    async def check(provider):
        for query, page in [(" ", 1), ("x" * 121, 1), ("Film", True), ("Film", 101)]:
            with pytest.raises(ValueError):
                await provider.search_movie_names(query, page=page)
        with pytest.raises(ValueError):
            await provider.person_movie_credits(True)
    run(handler, check)


def test_director_selection_uses_exact_job_and_includes_adult_films():
    crew = [{"id": 1, "job": "Director"}, {"id": 2, "job": "Producer"},
            {"id": 3, "job": "Director of Photography"}, {"id": 1, "job": "Director"},
            {"id": 4, "job": "Director", "adult": True}]
    assert director_movie_ids(crew) == [1, 4]
    assert director_movie_ids([]) == []
    assert acting_movie_ids([{"id": 4, "adult": True}]) == [4]
