from abc import ABC, abstractmethod

from ..completion import ChatCompletion, LegacyCompletion


class Executor(ABC):
    def __init__(self, context):
        self.context = context

    @abstractmethod
    async def execute(self):
        pass

    async def _generate_chat_completion(self, messages, parameters):
        completion = await ChatCompletion.generate(messages, parameters)
        self.context.increment_cost(completion.cost)
        return completion

    async def _generate_legacy_completion(self, prompt, parameters):
        completion = await LegacyCompletion.generate(prompt, parameters)
        self.context.increment_cost(completion.cost)
        return completion
