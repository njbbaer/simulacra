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
        self.context.add_cost(completion.cost)
        self._set_stats(completion)
        return completion.content.strip()

    async def _generate_legacy_completion(self, prompt, parameters):
        completion = await LegacyCompletion.generate(prompt, parameters)
        self.context.add_cost(completion.cost)
        return completion.content.strip()

    def _set_stats(self, completion):
        self.context.last_cost = completion.cost
        self.context.last_prompt_tokens = completion.prompt_tokens
        self.context.last_completion_tokens = completion.completion_tokens
