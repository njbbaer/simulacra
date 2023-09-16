import openai
import readline
from ruamel.yaml.scalarstring import LiteralScalarString

from src.context import Context
from src.llm import OpenAI


class Simulacrum:
    def __init__(self, context_file):
        self.context = Context(context_file)
        self.llm = OpenAI()

    def chat(self, user_input=None):
        self.context.load()
        if user_input:
            self.context.add_message('user', user_input)
            self.context.save()
        response = self._fetch_chat_response()
        self.context.add_message('assistant', response)
        self.context.save()
        return response

    def integrate_memory(self):
        self.context.load()
        response = self._fetch_integration_response()
        self.context.create_conversation(response)
        self.context.save()
        return response

    def clear_messages(self, n=None):
        self.context.load()
        self.context.clear_messages(n)
        self.context.save()

    def _fetch_chat_response(self):
        messages = [
            {
                'role': 'system',
                'content': self.context.chat_prompt,
            },
        ]
        messages.extend(self.context.current_messages)
        return self.llm.fetch_completion(messages)

    def _fetch_integration_response(self):
        content = 'Integrate the following new information:\n\n' \
            + '\n\n'.join([
                f'{message["role"]}:\n\n{message["content"]}'
                for message in self.context.current_messages
            ])
        messages = [
            {'role': 'system', 'content': self.context.memory_integration_prompt},
            {'role': 'assistant', 'content': self.context.current_memory_state},
            {'role': 'user', 'content': LiteralScalarString(content)},
            {'role': 'system', 'content': self.context.memory_integration_prompt},
        ]
        return self.llm.fetch_completion(messages, temperature=0.0)
