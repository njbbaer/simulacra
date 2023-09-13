import openai
import backoff

from src.logger import Logger


class LLM:
    def __init__(self, parameters={}):
        self.parameters = parameters
        self.logger = Logger('log.yml')


class OpenAI(LLM):
    DEFAULT_PARAMETERS = {
        'model': 'gpt-4',
    }

    @backoff.on_exception(backoff.expo, openai.error.RateLimitError)
    def complete(self, messages, **kwargs):
        parameters = {
            **self.DEFAULT_PARAMETERS,
            **self.parameters,
            **kwargs,
        }
        self.logger.record(messages, parameters)
        response = openai.ChatCompletion.create(
            **parameters,
            messages=messages,
        )['choices'][0]['message']['content']
        self.logger.attach_response(response)
        return response
