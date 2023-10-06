import openai

from src.logger import Logger


class OpenAI:
    MODEL = "gpt-4"

    def __init__(self, parameters={}):
        self.parameters = parameters
        self.logger = Logger("log.yml")

    async def fetch_completion(self, messages, **kwargs):
        parameters = self._get_merged_parameters(overrides=kwargs)
        response = await openai.ChatCompletion.acreate(**parameters, messages=messages)
        response_content = response["choices"][0]["message"]["content"]
        if response["choices"][0]["finish_reason"] == "length":
            raise Exception("Response exceeded maximum length")
        self.logger.log(parameters, messages, response_content)
        return response_content

    def _get_merged_parameters(self, overrides={}):
        return {
            "model": self.MODEL,
            "stop": "---",
            **self.parameters,
            **overrides,
        }
