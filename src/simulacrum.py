import re

from .context import Context
from .lm_executors import ChatExecutor, TitleExecutor


class Simulacrum:
    def __init__(self, context_file):
        self.context = Context(context_file)
        self.last_cost = None
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        self.warned_about_cost = False

    async def chat(self, user_input, user_name, image_url):
        self.context.load()
        if user_input:
            user_input = self._apply_attribution(user_input, user_name)
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

    def trim_messages(self, n=None):
        self.context.load()
        self.context.trim_messages(n)
        self.context.save()

    def reset_conversation(self):
        self.context.load()
        self.context.reset_conversation()
        self.context.save()
        self.warned_about_cost = False

    def add_conversation_fact(self, fact):
        self.context.load()
        self.context.add_conversation_fact(fact)
        self.context.save()

    def undo_last_user_message(self):
        self.context.load()
        num_messages = len(self.context.conversation_messages)
        for _ in range(num_messages):
            message = self.context.conversation_messages.pop()
            if message["role"] == "user":
                break
        self.context.save()

    def has_messages(self):
        self.context.load()
        return len(self.context.conversation_messages) > 0

    def get_conversation_cost(self):
        self.context.load()
        return self.context.conversation_cost

    async def generate_title(self):
        self.context.load()
        completion = await TitleExecutor(self.context).execute()
        return completion.content

    def _filter_hidden(self, response):
        response = re.sub(r"<THINK>.*?</>", "", response, flags=re.DOTALL)
        return response.strip()

    def _set_stats(self, completion):
        self.last_cost = completion.cost
        self.last_prompt_tokens = completion.prompt_tokens
        self.last_completion_tokens = completion.completion_tokens

    def _apply_attribution(self, input, name):
        attribute_messages = self.context.vars.get("attribute_messages")
        if attribute_messages and name:
            if isinstance(attribute_messages, dict) and name in attribute_messages:
                name = attribute_messages[name]
            input = f"{name}: {input}"
        return input
