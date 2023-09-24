import openai
import backoff

from src.logger import Logger


class OpenAI:
    MODEL = 'gpt-4'
    MAX_TOKENS = 8192

    def __init__(self, parameters={}):
        self.parameters = parameters
        self.logger = Logger('log.yml')
        self.tokens = 0

    @backoff.on_exception(backoff.expo, openai.error.RateLimitError)
    async def fetch_completion(self, messages, **kwargs):
        parameters = self._get_parameters(kwargs)
        response = await openai.ChatCompletion.acreate(**parameters, messages=messages)
        response_content = response['choices'][0]['message']['content']
        self.logger.log(parameters, messages, response_content)
        return response_content

    def _get_parameters(self, overrides={}):
        return {
            'model': self.MODEL,
            **self.parameters,
            **overrides,
        }
