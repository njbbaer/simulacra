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
    def fetch_completion(self, messages, **kwargs):
        parameters = self._get_parameters(kwargs)
        self.logger.record(messages, parameters)
        response = openai.ChatCompletion.create(**parameters, messages=messages)
        response_content = response['choices'][0]['message']['content']
        self.logger.attach_response(response_content)
        self.tokens = response['usage']['total_tokens']
        return response_content

    def _get_parameters(self, overrides={}):
        return {
            'model': self.MODEL,
            **self.parameters,
            **overrides,
        }

    @property
    def token_utilization_percentage(self):
        return self.tokens / self.MAX_TOKENS * 100
