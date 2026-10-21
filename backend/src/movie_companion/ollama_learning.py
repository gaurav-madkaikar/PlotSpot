"""Learner-owned first Ollama call; not connected to the public API yet."""

import httpx


async def chat_once(
    client: httpx.AsyncClient, *, model: str, prompt: str,
    response_schema: dict | None = None,
    think: bool | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Request one non-streaming reply and return nonempty assistant text.

    Preserve HTTP errors. Raise ValueError for missing, empty, or non-string
    message content. The caller supplies the local-only client and timeout.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if think is not None:
        if type(think) is not bool:
            raise ValueError("Thinking flag must be boolean")
        payload["think"] = think
    if response_schema is not None:
        payload["format"] = response_schema
        payload["options"] = {"temperature": 0, "seed": 7}
    if max_output_tokens is not None:
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4096:
            raise ValueError("Output token limit must be between 1 and 4096")
        payload.setdefault("options", {})["num_predict"] = max_output_tokens
    response = await client.post(
        "/api/chat",
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON response object")
    message = data.get("message")
    if not isinstance(message, dict):
        raise ValueError("Expected an assistant message object")
    message_content = message.get("content")
    if not isinstance(message_content, str):
        raise ValueError("Expected JSON response with string content, got non-string")
    message_content = message_content.strip()
    if not message_content:
        raise ValueError("Expected JSON response with string content, got empty string")
    return message_content
