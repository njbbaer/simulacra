from abc import ABC, abstractmethod

from src.llm import OpenAI


class PromptExecutor(ABC):
    def __init__(self, context):
        self.context = context
        self.llm = OpenAI()

    @abstractmethod
    async def execute(self):
        pass
