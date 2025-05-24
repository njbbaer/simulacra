import asyncio
import os

import backoff
import httpx

from .chat_completion import ChatCompletion
from .logger import Logger


class RateLimitExceeded(Exception):
    def __init__(self, message="API rate limit exceeded"):
        super().__init__(message)


class OpenRouterAPIClient:
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.logger = Logger("log.yml")

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def _prepare_body(self, messages, parameters, provider=None):
        body = {"messages": messages, **parameters}
        if provider:
            body["provider"] = {"only": [provider]}
        return body

    async def request_completion(self, messages, parameters, provider=None):
        body = self._prepare_body(messages, parameters, provider)
        try:
            completion_data = await self._fetch_completion_data(body)
            completion = ChatCompletion(completion_data)
            self.logger.log(parameters, messages, completion.content)
            return completion
        except httpx.ReadTimeout:
            raise Exception("Request timed out")

    @backoff.on_exception(backoff.expo, RateLimitExceeded, max_tries=10)
    async def _fetch_completion_data(self, body):
        async with httpx.AsyncClient(timeout=30) as client:
            completion_response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self._get_headers(),
                json=body,
            )
            completion_response.raise_for_status()
            completion_data = completion_response.json()

            if "error" in completion_data:
                if completion_data["error"].get("code") == 429:
                    raise RateLimitExceeded()
                raise Exception(completion_data["error"])

            details_data = await self._fetch_details(completion_data["id"])
            return {**completion_data, "details": details_data["data"]}

    async def _fetch_details(self, generation_id: str):
        details_url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
        async with httpx.AsyncClient(timeout=3) as client:
            for _ in range(10):
                try:
                    response = await client.get(
                        details_url, headers=self._get_headers()
                    )
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPError:
                    await asyncio.sleep(0.5)
            raise Exception("Details request timed out")
