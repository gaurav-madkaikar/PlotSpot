"""Inspect revision-attributed movie source metadata; no ingestion or generation."""

import argparse
import asyncio

import httpx

from movie_companion.wikipedia_source import fetch_movie_source


async def main(show_text):
    async with httpx.AsyncClient(
        base_url="https://en.wikipedia.org", timeout=30,
        follow_redirects=False, trust_env=False,
        headers={"User-Agent": "MovieCompanionLearning/0.1 (local educational source reader)"},
    ) as client:
        source = await fetch_movie_source(client, movie_id=157336)
    print(f"Source: {source.source_label}\nReference: {source.source_ref}")
    print(f"Revision: {source.revision}\nCharacters: {len(source.text)}\nSpoiler status: {source.spoiler_status}")
    if show_text:
        print("UNCLASSIFIED ARTICLE TEXT — MAY CONTAIN STORY SPOILERS")
        print(source.text[:1000])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-text", action="store_true", help="Opt into a potentially spoiler-containing text preview")
    asyncio.run(main(parser.parse_args().show_text))
