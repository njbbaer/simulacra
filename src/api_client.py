import os

import httpx


class ApiClient:
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

    def __init__(self, name, instruction_template=None):
        self.name = name or "openai"
        self.instruction_template = instruction_template

    @property
    def api_url(self):
        return self.CONFIG[self.name]["api_url"]

    @property
    def api_key(self):
        return os.environ.get(self.CONFIG[self.name]["api_key_env"])

    async def call_api(self, messages, parameters):
        body = {"messages": messages, **parameters}
        if self.instruction_template:
            body["instruction_template"] = self.instruction_template

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        async with httpx.AsyncClient(timeout=120) as client:
            url = f"{self.api_url}/v1/chat/completions"
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()
