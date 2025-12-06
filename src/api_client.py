import asyncio
import os
from collections.abc import Coroutine
from typing import Any

import backoff
import httpx

from .chat_completion import ChatCompletion
from .logger import Logger

current_api_task: asyncio.Task | None = None


class OpenRouterAPIClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.logger = Logger("log.yml")

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _prepare_body(
        self,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return {"messages": messages, **parameters}

    async def request_completion(
        self,
        messages: list[dict[str, Any]],
        parameters: dict[str, Any],
    ) -> ChatCompletion:
        body = self._prepare_body(messages, parameters)
        try:
            completion_data = await self._execute_with_cancellation(
                self._fetch_completion_data(body)
            )
            completion = ChatCompletion(completion_data)
            self.logger.log(parameters, messages, completion.content)
            return completion
        except httpx.ReadTimeout as err:
            raise Exception("Request timed out") from err

    async def _execute_with_cancellation[T](self, coro: Coroutine[Any, Any, T]) -> Any:
        task = asyncio.create_task(coro)
        global current_api_task
        current_api_task = task
        try:
            return await task
        finally:
            current_api_task = None

    @backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=5)
    async def _fetch_completion_data(self, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=60)) as client:
            completion_response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self._get_headers(),
                json=body,
            )
            completion_response.raise_for_status()
            completion_data = completion_response.json()
            details_data = await self._fetch_details(completion_data["id"])
            return {**completion_data, "details": details_data["data"]}

    async def _fetch_details(self, generation_id: str) -> dict[str, Any]:
        details_url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
        async with httpx.AsyncClient() as client:
            for _ in range(10):
                try:
                    response = await client.get(
                        details_url, headers=self._get_headers()
                    )
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPError:
                    await asyncio.sleep(0.5)
            return {"data": {"total_cost": 0.0, "cache_discount": 0.0}}
