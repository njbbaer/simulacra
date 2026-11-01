import os
from typing import Any

import httpx

from .utilities import retry_on

API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = httpx.Timeout(10, read=60)
APP_HEADERS = {
    "HTTP-Referer": "https://github.com/njbbaer/simulacra",
    "X-OpenRouter-Title": "Simulacra",
}


@retry_on(httpx.HTTPError, 3)
async def fetch_completion(
    body: dict[str, Any],
    request_timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    return await _post("chat/completions", body, request_timeout)


@retry_on(httpx.HTTPError, 3)
async def fetch_transcription(body: dict[str, Any]) -> dict[str, Any]:
    return await _post("audio/transcriptions", body, DEFAULT_TIMEOUT)


async def _post(
    path: str, body: dict[str, Any], request_timeout: float | httpx.Timeout
) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.post(
            f"{API_BASE}/{path}",
            headers={"Authorization": f"Bearer {api_key}", **APP_HEADERS},
            json=body,
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise RuntimeError(
                f"Non-JSON response from OpenRouter ({response.status_code})"
            ) from None
        if "error" in data:
            raise RuntimeError(data["error"])
        response.raise_for_status()
        return data
