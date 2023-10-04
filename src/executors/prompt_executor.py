from abc import ABC

from src.llm import OpenAI


class PromptExecutor(ABC):
    def __init__(self, context):
        self.context = context
        self.llm = OpenAI()

    async def execute(self):
        messages = self.build_messages()
        return await self.llm.fetch_completion(messages)
