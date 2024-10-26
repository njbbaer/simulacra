import os

import httpx

from .chat_completion import OpenRouterChatCompletion
from .logger import Logger


class OpenRouterAPIClient:
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    ENV_KEY = "OPENROUTER_API_KEY"
    TIMEOUT = 30

    def __init__(self):
        self.api_key = os.environ.get(self.ENV_KEY)
        self.logger = Logger("log.yml")

    def get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def prepare_body(self, messages, parameters):
        return {"messages": messages, **parameters}

    async def request_completion(self, messages, parameters, pricing):
        body = self.prepare_body(messages, parameters)
        try:
            completion_data = await self.get_completion_data(body)
            completion = OpenRouterChatCompletion(completion_data, pricing)
            self.logger.log(parameters, messages, completion.content)
            return completion
        except httpx.ReadTimeout:
            raise Exception("Request timed out")

    async def get_completion_data(self, body):
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            completion_response = await client.post(
                self.API_URL, headers=self.get_headers(), json=body
            )
            completion_response.raise_for_status()
            completion_data = completion_response.json()
            if "error" in completion_data:
                raise Exception(completion_data["error"])

            details_data = await self._poll_details(client, completion_data["id"])
            return {**completion_data, "details": details_data["data"]}

    async def _poll_details(self, client, generation_id, max_attempts=10):
        details_url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"

        for _ in range(max_attempts):
            details_response = await client.get(details_url, headers=self.get_headers())
            if details_response.status_code == 200:
                return details_response.json()

        raise TimeoutError("Details not available after maximum attempts")
