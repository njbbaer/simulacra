import re

from .context import Context
from .executors import ChatExecutor


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
        speech = self._filter_hidden(content)
        return speech

    async def new_conversation(self):
        self.context.load()
        self.context.new_conversation()
        self.context.save()
        self.warned_about_cost = False

    def clear_messages(self, n=None):
        self.context.load()
        self.context.clear_messages(n)
        self.context.save()

    def reset_current_conversation(self):
        self.context.load()
        self.context.reset_current_conversation()
        self.context.save()
        self.warned_about_cost = False

    def add_conversation_detail(self, detail):
        self.context.load()
        self.context.add_conversation_detail(detail)
        self.context.save()

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

    def _filter_hidden(self, response):
        response = re.sub(r"<THINK>.*?</>", "", response, flags=re.DOTALL)
        return response.strip()

    def _set_stats(self, completion):
        self.last_cost = completion.cost
        self.last_prompt_tokens = completion.prompt_tokens
        self.last_completion_tokens = completion.completion_tokens
