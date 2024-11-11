import re
import textwrap

from .context import Context
from .lm_executors import ChatExecutor


class Simulacrum:
    def __init__(self, context_file):
        self.context = Context(context_file)
        self.last_completion = None
        self.cost_warning_sent = False
        self.instruction_text = None

    async def chat(self, user_input, user_name, image_url):
        self.context.load()
        if user_input:
            user_input = self._inject_instruction(user_input)
            self.context.add_message("user", user_input, image_url)
        self.context.save()
        completion = await ChatExecutor(self.context).execute()
        self.last_completion = completion
        content = completion.content.strip()
        self.context.add_message("assistant", content)
        self.context.save()
        content = self._strip_tag(content, "playwright")
        speech = self._strip_tag(content, "think")
        return speech

    async def new_conversation(self):
        self.context.load()
        self.context.new_conversation()
        self.context.save()
        self.cost_warning_sent = False

    def reset_conversation(self):
        self.context.load()
        self.context.reset_conversation()
        self.context.save()
        self.cost_warning_sent = False

    def add_conversation_fact(self, fact_text):
        self.context.load()
        self.context.add_conversation_fact(fact_text)
        self.context.save()

    def apply_instruction(self, instruction_text):
        self.instruction_text = instruction_text

    def undo_last_messages_by_role(self, role):
        self.context.load()
        num_messages = len(self.context.conversation_messages)
        for _ in range(num_messages):
            message = self.context.conversation_messages.pop()
            if message["role"] == role:
                break
        self.context.save()

    def has_messages(self):
        self.context.load()
        return len(self.context.conversation_messages) > 0

    def get_conversation_cost(self):
        self.context.load()
        return self.context.conversation_cost

    @property
    def last_message_role(self):
        self.context.load()
        return self.context.conversation_messages[-1]["role"]

    def _strip_tag(self, content, tag):
        content = re.sub(rf"<{tag}.*?>.*?</{tag}>", "", content, flags=re.DOTALL)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    def _inject_instruction(self, text):
        if self.instruction_text:
            text = textwrap.dedent(
                f"""
                {text}

                <instruct>
                {self.instruction_text}
                </instruct>
                """
            )
            self.instruction_text = None
        return text
