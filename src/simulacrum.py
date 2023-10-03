import re
import tiktoken

from src.context import Context
from src.executors import ChatExecutor, MemoryIntegrationExecutor


class Simulacrum:
    def __init__(self, context_file):
        self.context = Context(context_file)

    async def chat(self, user_input=None):
        self.context.load()
        if user_input:
            self.context.add_message('user', user_input)
        response = await ChatExecutor(self.context).execute()
        self.context.add_message('assistant', response)
        self.context.save()
        return self._extract_speech(response)

    async def integrate_memory(self):
        self.context.load()
        memory_chunks = await MemoryIntegrationExecutor(self.context).execute()
        self.context.new_conversation(memory_chunks)
        self.context.save()

    def append_memory(self, text):
        self.context.load()
        self.context.append_memory('\n\n' + text)
        self.context.save()

    def clear_messages(self, n=None):
        self.context.load()
        self.context.clear_messages(n)
        self.context.save()

    def undo_last_user_message(self):
        self.context.load()
        num_messages = len(self.context.current_messages)
        for i in range(num_messages):
            message = self.context.current_messages.pop()
            if message['role'] == 'user':
                break
        self.context.save()

    def estimate_utilization_percentage(self):
        MAX_TOKENS = 8192
        ESTIMATED_RESPONSE_TOKENS = 500
        BASE_TOKENS = 3
        BASE_TOKENS_PER_MESSAGE = 4

        self.context.load()
        executor = ChatExecutor(self.context)
        messages = executor.build_chat_messages()
        encoding = tiktoken.encoding_for_model("gpt-4")
        num_request_tokens = BASE_TOKENS
        for message in messages:
            num_request_tokens += len(encoding.encode(message['content'])) + BASE_TOKENS_PER_MESSAGE
        return num_request_tokens / (MAX_TOKENS - ESTIMATED_RESPONSE_TOKENS) * 100

    def has_messages(self):
        self.context.load()
        return len(self.context.current_messages) > 0

    def _extract_speech(self, response):
        match = re.search(r'<(?:MESSAGE|SPEAK)>(.*?)</(?:MESSAGE|SPEAK)>', response, re.DOTALL)
        return match.group(1) if match else response
