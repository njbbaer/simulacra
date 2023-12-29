import re

from .context import Context
from .executors import ChatExecutor, MemoryIntegrationExecutor


class Simulacrum:
    def __init__(self, context_file):
        self.context = Context(context_file)
        self.last_cost = None
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        self.warned_about_cost = False

    async def chat(self, user_input, image_url):
        self.context.load()
        if user_input:
            self.context.add_message("user", user_input, image_url)
        completion = await ChatExecutor(self.context).execute()
        content = completion.content.strip()
        self._set_stats(completion)
        self.context.add_message("assistant", content)
        self.context.save()
        speech = self._extract_speech(content)
        action = self._extract_action(content)
        return speech, action

    async def new_conversation(self, integrate_memory=False):
        self.context.load()
        if integrate_memory:
            memory = await MemoryIntegrationExecutor(self.context).execute()
        else:
            memory = self.context.current_memory_chunks
        self.context.new_conversation(memory)
        self.context.save()
        self.warned_about_cost = False

    def append_memory(self, text):
        self.context.load()
        self.context.append_memory("\n\n" + text)
        self.context.save()

    def clear_messages(self, n=None):
        self.context.load()
        self.context.clear_messages(n)
        self.context.save()
        self.warned_about_cost = False

    def undo_last_user_message(self):
        self.context.load()
        num_messages = len(self.context.current_messages)
        for _ in range(num_messages):
            message = self.context.current_messages.pop()
            if message["role"] == "user":
                break
        self.context.save()

    def has_messages(self):
        self.context.load()
        return len(self.context.current_messages) > 0

    def get_current_conversation_cost(self):
        self.context.load()
        return self.context.current_conversation["cost"]

    def _extract_speech(self, response):
        match = re.search(
            r"<(?:MESSAGE|SPEAK)>(.*?)</(?:MESSAGE|SPEAK)>", response, re.DOTALL
        )
        return match.group(1) if match else response

    def _extract_action(self, response):
        match = re.search(r"<(?:ACT)>(.*?)</(?:ACT)>", response, re.DOTALL)
        return match.group(1) if match else None

    def _set_stats(self, completion):
        self.last_cost = completion.cost
        self.last_prompt_tokens = completion.prompt_tokens
        self.last_completion_tokens = completion.completion_tokens
