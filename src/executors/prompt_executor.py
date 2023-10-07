from abc import ABC, abstractmethod

from ..openai_completion import OpenAICompletion


class PromptExecutor(ABC):
    def __init__(self, context):
        self.context = context

    async def _fetch_completion(self, messages, parameters=None):
        completion = await OpenAICompletion.fetch_completion(messages, parameters)
        self.context.add_cost(completion.cost)
        return completion.content

    @abstractmethod
    async def execute(self):
        pass
