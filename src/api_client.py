import os
from typing import Any

import backoff
import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT = httpx.Timeout(10, read=60)


@backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=5)
async def fetch_completion(
    body: dict[str, Any],
    request_timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        response.raise_for_status()
        return data
