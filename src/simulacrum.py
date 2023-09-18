import re

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
        return self._extract_speech(response)

    def integrate_memory(self):
        self.context.load()
        response = self._fetch_integration_response()
        self.context.new_conversation(response)
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
                'content': self._format_chat_prompt(),
            },
        ]
        messages.extend(self.context.current_messages)
        return self.llm.fetch_completion(messages)

    def _extract_speech(self, response):
        match = re.search(r'<SPEAKS>(.*?)</SPEAKS>', response)
        return match.group(1) if match else response

    def _fetch_integration_response(self):
        content = (
            f'Most recent conversation: \n\n{self._format_conversation_history()}\n\n'
            f'---\n\nPrevious memory state:\n\n{self.context.current_memory}'
        )
        prompt = self.context.memory_integration_prompt
        formatted_messages = [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': content},
            {'role': 'system', 'content': prompt},
        ]
        return self.llm.fetch_completion(formatted_messages, temperature=0.0)

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg['role'])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return '\n\n'.join(messages)

    def _format_chat_prompt(self):
        name = self.context.get_name('assistant')
        memory = f"{name}'s Memory:\n\n{self.context.current_memory}"
        return self.context.chat_prompt + '\n\n---\n\n' + memory