"""Inspect name API response shapes with the locally configured token."""
import argparse
import asyncio
import json

import httpx

from movie_companion.settings import get_settings
from movie_companion.tmdb_client import TmdbClient


async def inspect(args):
    token = get_settings().tmdb_read_token
    if not token:
        raise ValueError("Configure the local TMDB read token first")
    async with httpx.AsyncClient(base_url="https://api.themoviedb.org/3", timeout=8,
        follow_redirects=False, headers={"Authorization": f"Bearer {token}"}) as http:
        provider = TmdbClient(http)
        method = provider.search_movie_names if args.kind == "movie" else provider.search_person_names
        result = await method(args.query, page=args.page)
        print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
        if args.person_id is not None:
            credits = await provider.person_movie_credits(args.person_id)
            print(json.dumps({"person_id": args.person_id,
                "acting_records": len(credits["cast"]), "crew_records": len(credits["crew"]),
                "crew_example": [{"id": r["id"], "title": r.get("title"), "job": r["job"]} for r in credits["crew"][:5]]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["movie", "person"])
    parser.add_argument("query")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--person-id", type=int)
    asyncio.run(inspect(parser.parse_args()))
