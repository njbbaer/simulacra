import os
from abc import ABC, abstractmethod

import httpx

from .chat_completion import AnthropicChatCompletion, OpenRouterChatCompletion


class APIClient(ABC):
    TIMEOUT = 60

    def __init__(self):
        self.api_key = os.environ.get(self.ENV_KEY)

    async def call_api(self, body):
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                self.API_URL, headers=self.get_headers(), json=body
            )
            response.raise_for_status()
            return response.json()

    @abstractmethod
    def get_headers(self):
        pass

    @staticmethod
    def create(client_type):
        if client_type == "openrouter":
            return OpenRouterAPIClient()
        elif client_type == "anthropic":
            return AnthropicAPIClient()
        else:
            raise ValueError(f"Unsupported client type: {client_type}")


class OpenRouterAPIClient(APIClient):
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    ENV_KEY = "OPENROUTER_API_KEY"

    async def call_api(self, messages, parameters, pricing):
        body = {"messages": messages, **parameters}
        response = await super().call_api(body)
        return OpenRouterChatCompletion(response, pricing)

    def get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}


class AnthropicAPIClient(APIClient):
    API_URL = "https://api.anthropic.com/v1/messages"
    ENV_KEY = "ANTHROPIC_API_KEY"

    async def call_api(self, messages, parameters, pricing):
        messages, system = self._transform_messages(messages)
        body = {"messages": messages, "system": system, **parameters}
        response = await super().call_api(body)
        return AnthropicChatCompletion(response, pricing)

    def get_headers(self):
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def _transform_messages(self, original_messages):
        messages = []
        system = []

        for message in original_messages:
            if message["role"] == "system":
                system.append({"type": "text", "text": message["content"]})
            else:
                messages.append(message)

        return messages, system
