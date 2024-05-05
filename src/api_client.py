import os

import httpx


class ApiClient:
    TIMEOUT = 120
    CONFIG = {
        "openai": {
            "api_url": "https://api.openai.com",
            "api_key_env": "OPENAI_API_KEY",
        },
        "openrouter": {
            "api_url": "https://openrouter.ai/api",
            "api_key_env": "OPENROUTER_API_KEY",
        },
    }

    def __init__(self, provider):
        self.provider = provider

    async def call_api(self, messages, parameters):
        body = {"messages": messages, **parameters}

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            url = f"{self.api_url}/v1/chat/completions"
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    @property
    def api_url(self):
        return self.CONFIG[self.provider]["api_url"]

    @property
    def api_key(self):
        var = self.CONFIG[self.provider]["api_key_env"]
        return os.environ.get(var)
