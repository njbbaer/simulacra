import os
from abc import ABC, abstractmethod

import httpx

from .chat_completion import AnthropicChatCompletion, OpenRouterChatCompletion
from .logger import Logger


class APIClient(ABC):
    TIMEOUT = 60

    def __init__(self):
        self.api_key = os.environ.get(self.ENV_KEY)
        self.logger = Logger("log.yml")

    @staticmethod
    def create(client_type):
        clients = {"openrouter": OpenRouterAPIClient, "anthropic": AnthropicAPIClient}
        if client_type not in clients:
            raise ValueError(f"Unsupported client type: {client_type}")
        return clients[client_type]()

    async def request_completion(self, messages, parameters, pricing):
        body = self.prepare_body(messages, parameters)
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                self.API_URL, headers=self.get_headers(), json=body
            )
            response.raise_for_status()
            completion = self.create_completion(response.json(), pricing)
            self.logger.log(parameters, messages, completion.content)
            return completion

    @abstractmethod
    def get_headers(self):
        pass

    @abstractmethod
    def prepare_body(self, messages, parameters):
        pass

    @abstractmethod
    def create_completion(self, response, pricing):
        pass


class OpenRouterAPIClient(APIClient):
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    ENV_KEY = "OPENROUTER_API_KEY"

    def get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def prepare_body(self, messages, parameters):
        return {"messages": messages, **parameters}

    def create_completion(self, response, pricing):
        return OpenRouterChatCompletion(response, pricing)


class AnthropicAPIClient(APIClient):
    API_URL = "https://api.anthropic.com/v1/messages"
    ENV_KEY = "ANTHROPIC_API_KEY"

    def get_headers(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
        }

    def prepare_body(self, messages, parameters):
        other_messages, system = self._transform_messages(messages)
        return {"messages": other_messages, "system": system, **parameters}

    def create_completion(self, response, pricing):
        return AnthropicChatCompletion(response, pricing)

    def _transform_messages(self, original_messages):
        messages = [msg for msg in original_messages if msg["role"] != "system"]
        system = []
        for msg in original_messages:
            if msg["role"] == "system":
                system.extend(msg["content"])

        return messages, system
