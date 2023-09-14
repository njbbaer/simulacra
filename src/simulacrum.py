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
        messages = self._render_chat_messages()
        response = self.llm.fetch_completion(messages)
        self.context.add_message('assistant', response)
        return response

    def retry(self):
        self.context.load()
        self.context.delete_messages(1)
        return self.chat()

    def integrate_memory(self):
        self.context.load()
        messages = self._render_memorizer_messages()
        response = self.llm.fetch_completion(messages, temperature=0.0)
        self.context.set_memory(response)
        self.context.clear_messages()
        return response

    def clear_messages(self):
        self.context.clear_messages()

    def _render_chat_messages(self):
        messages = [
            {
                'role': 'system',
                'content': self.context.chat_prompt,
            },
        ]
        messages.extend(self.context.chat_messages)
        return messages

    def _render_memorizer_messages(self):
        content = 'Integrate the following new information:\n\n' \
            + '\n\n'.join([
                f'{message["role"]}:\n\n{message["content"]}'
                for message in self.context.chat_messages
            ])
        return [
            {'role': 'system', 'content': self.context.memorizer_prompt},
            {'role': 'assistant', 'content': self.context.current_memory},
            {'role': 'user', 'content': LiteralScalarString(content)},
            {'role': 'system', 'content': self.context.memorizer_prompt},
        ]
