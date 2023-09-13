import openai
import backoff

from src.logger import Logger


class LLM:
    def __init__(self, parameters={}):
        self.parameters = parameters
        self.logger = Logger('log.yml')

    def merge_parameters(self, overrides={}):
        return {
            **self.DEFAULTS,
            **self.parameters,
            **overrides,
        }


class OpenAI(LLM):
    DEFAULTS = {
        'model': 'gpt-4',
    }

    @backoff.on_exception(backoff.expo, openai.error.RateLimitError)
    def fetch_completion(self, messages, **kwargs):
        parameters = self.merge_parameters(kwargs)
        self.logger.record(messages, parameters)
        response = openai.ChatCompletion.create(**parameters, messages=messages)
        response_content = response['choices'][0]['message']['content']
        self.logger.attach_response(response_content)
        return response_content
