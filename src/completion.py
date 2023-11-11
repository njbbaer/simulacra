import asyncio
from abc import ABC, abstractmethod

import openai

from .logger import Logger


class Completion(ABC):
    API_CALL_TIMEOUT = 120

    MODEL_PRICINGS = {
        "gpt-4": [0.03, 0.06],
        "gpt-4-0314": [0.03, 0.06],
        "gpt-4-1106-preview": [0.01, 0.02],
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

    @classmethod
    async def _call_with_timeout(cls, api_call_coroutine):
        try:
            return await asyncio.wait_for(api_call_coroutine, cls.API_CALL_TIMEOUT)
        except asyncio.TimeoutError:
            raise Exception("API call timed out")


class ChatCompletion(Completion):
    COMPLETION_TYPE = openai.ChatCompletion

    @staticmethod
    async def _call_api(messages, parameters):
        api_call = openai.ChatCompletion.acreate(**parameters, messages=messages)
        return await Completion._call_with_timeout(api_call)

    @property
    def content(self):
        return self.choice["message"]["content"]


class LegacyCompletion(Completion):
    COMPLETION_TYPE = openai.Completion

    @staticmethod
    async def _call_api(prompt, parameters):
        api_call = openai.Completion.acreate(**parameters, prompt=prompt)
        return await Completion._call_with_timeout(api_call)

    @property
    def content(self):
        return self.choice["text"]
