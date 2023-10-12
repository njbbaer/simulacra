from abc import ABC, abstractmethod

from ..completion import ChatCompletion, LegacyCompletion


class Executor(ABC):
    def __init__(self, context):
        self.context = context

    @abstractmethod
    async def execute(self):
        pass

    async def _generate_chat_completion(self, messages, parameters):
        return await self._generate_completion(messages, parameters, ChatCompletion)

    async def _generate_legacy_completion(self, prompt, parameters):
        return await self._generate_completion(prompt, parameters, LegacyCompletion)

    async def _generate_completion(self, content, parameters, completion_type):
        completion = await completion_type.generate(content, parameters)
        self.context.add_cost(completion.cost)
        return completion.content.strip()
