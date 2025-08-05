import asyncio
import os
from typing import Any, Coroutine, Dict, List, Optional

import backoff
import httpx

from .chat_completion import ChatCompletion
from .logger import Logger

last_api_call_task: Optional[asyncio.Task] = None


class RateLimitExceeded(Exception):
    def __init__(self, message: str = "API rate limit exceeded") -> None:
        super().__init__(message)


class OpenRouterAPIClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.logger = Logger("log.yml")

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _prepare_body(
        self,
        messages: List[Dict[str, Any]],
        parameters: Dict[str, Any],
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {"messages": messages, **parameters}
        if provider:
            body["provider"] = {"only": [provider]}
        return body

    async def request_completion(
        self,
        messages: List[Dict[str, Any]],
        parameters: Dict[str, Any],
        provider: Optional[str] = None,
    ) -> ChatCompletion:
        body = self._prepare_body(messages, parameters, provider)
        try:
            completion_data = await self._execute_with_cancellation(
                self._fetch_completion_data(body)
            )
            completion = ChatCompletion(completion_data)
            self.logger.log(parameters, messages, completion.content)
            return completion
        except httpx.ReadTimeout:
            raise Exception("Request timed out")

    async def _execute_with_cancellation[T](self, coro: Coroutine[Any, Any, T]) -> Any:
        task = asyncio.create_task(coro)
        global last_api_call_task
        last_api_call_task = task
        try:
            result = await task
            return result
        finally:
            last_api_call_task = None

    @backoff.on_exception(backoff.expo, RateLimitExceeded, max_tries=10)
    async def _fetch_completion_data(self, body: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            completion_response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self._get_headers(),
                json=body,
            )
            completion_data = completion_response.json()

            if "error" in completion_data:
                if completion_data["error"].get("code") == 429:
                    raise RateLimitExceeded()
                raise Exception(completion_data["error"])

            details_data = await self._fetch_details(completion_data["id"])
            return {**completion_data, "details": details_data["data"]}

    async def _fetch_details(self, generation_id: str) -> Dict[str, Any]:
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
            return {"data": {"total_cost": 0.0, "cache_discount": 0.0}}
