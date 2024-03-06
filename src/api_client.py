import httpx


class ApiClient:
    def __init__(self, base_url=None, instruction_template=None, api_key=None):
        self.base_url = base_url or "https://api.openai.com"
        self.instruction_template = instruction_template
        self.api_key = api_key

    async def call_api(self, messages, parameters):
        body = {"messages": messages, **parameters}
        if self.instruction_template:
            body["instruction_template"] = self.instruction_template

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        async with httpx.AsyncClient(timeout=120) as client:
            url = f"{self.base_url}/v1/chat/completions"
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()
