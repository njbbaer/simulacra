import openai

from .logger import Logger


class OpenAICompletion:
    DEFAULT_PARAMETERS = {"model": "gpt-4"}
    MODEL_PRICINGS = {
        "gpt-4": [0.03, 0.06],
        "gpt-3.5-turbo": [0.0015, 0.002],
        "gpt-3.5-turbo-16k": [0.003, 0.004],
    }

    def __init__(self, response, model):
        self.response = response
        self.pricing = self.MODEL_PRICINGS[model]

    @classmethod
    async def fetch_completion(cls, messages, parameters=None):
        merged_params = {**cls.DEFAULT_PARAMETERS, **(parameters or {})}
        response = await openai.ChatCompletion.acreate(
            **merged_params, messages=messages
        )
        completion = OpenAICompletion(response, merged_params["model"])
        if completion.finish_reason == "length":
            raise Exception("Response exceeded maximum length")
        Logger("log.yml").log(parameters, messages, completion.content)
        return completion

    @property
    def content(self):
        return self.response["choices"][0]["message"]["content"]

    @property
    def finish_reason(self):
        return self.response["choices"][0]["finish_reason"]

    @property
    def prompt_tokens(self):
        return self.response["usage"]["prompt_tokens"]

    @property
    def completion_tokens(self):
        return self.response["usage"]["completion_tokens"]

    @property
    def cost(self):
        return (self.prompt_tokens / 1000 * self.pricing[0]) + (
            self.completion_tokens / 1000 * self.pricing[1]
        )
