"""Run after completing the chat_once exercise; use only local inference."""

import asyncio

import httpx

from movie_companion.ollama_learning import chat_once


async def main():
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=120,
        follow_redirects=False, trust_env=False,
    ) as client:
        answer = await chat_once(
            client,
            model="llama3.2:3b",
            prompt="In two short sentences, explain what a text embedding is to a beginner.",
        )
        print(answer)


if __name__ == "__main__":
    asyncio.run(main())
