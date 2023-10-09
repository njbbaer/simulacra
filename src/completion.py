from abc import ABC, abstractmethod

import openai

from .logger import Logger


class Completion(ABC):
    MODEL_PRICINGS = {
        "gpt-4": [0.03, 0.06],
        "gpt-3.5-turbo": [0.0015, 0.002],
        "gpt-3.5-turbo-16k": [0.003, 0.004],
        "gpt-3.5-turbo-instruct": [0.0015, 0.002],
    }

    def __init__(self, response, model):
        self.response = response
        self.pricing = self.MODEL_PRICINGS[model]
        self.logger = Logger("log.yml")
        self._validate()

    @classmethod
    async def generate(cls, content, parameters):
        response = await cls._call_api(content, parameters)
        completion = cls(response, parameters["model"])
        completion.logger.log(parameters, content, completion.content)
        return completion

    @staticmethod
    @abstractmethod
    async def _call_api(_, parameters):
        pass

    @property
    @abstractmethod
    def content(self):
        pass

    @property
    def choice(self):
        return self.response["choices"][0]

    @property
    def prompt_tokens(self):
        return self.response["usage"]["prompt_tokens"]

    @property
    def completion_tokens(self):
        return self.response["usage"]["completion_tokens"]

    @property
    def finish_reason(self):
        return self.choice["finish_reason"]

    @property
    def cost(self):
        return (self.prompt_tokens / 1000 * self.pricing[0]) + (
            self.completion_tokens / 1000 * self.pricing[1]
        )

    def _validate(self):
        if self.finish_reason == "length":
            raise Exception("Response exceeded maximum length")


class ChatCompletion(Completion):
    COMPLETION_TYPE = openai.ChatCompletion

    @staticmethod
    async def _call_api(messages, parameters):
        return await openai.ChatCompletion.acreate(**parameters, messages=messages)

    @property
    def content(self):
        return self.choice["message"]["content"]


class LegacyCompletion(Completion):
    COMPLETION_TYPE = openai.Completion

    @staticmethod
    async def _call_api(prompt, parameters):
        return await openai.Completion.acreate(**parameters, prompt=prompt)

    @property
    def content(self):
        return self.choice["text"]
