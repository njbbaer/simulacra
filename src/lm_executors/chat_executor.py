import copy
from typing import Any

import jinja2
import yaml

from ..api_client import OpenRouterAPIClient
from ..chat_completion import ChatCompletion
from ..message import Message
from ..utilities import make_base64_loader


class ChatExecutor:
    TEMPLATE_PATH = "src/lm_executors/chat_executor_template.j2"

    def __init__(self, context) -> None:
        self.context = context

    async def execute(self, params: dict[str, Any] | None = None) -> ChatCompletion:
        client = OpenRouterAPIClient()

        merged_params = {**self.context.api_params}
        if params:
            merged_params.update(params)

        completion = await client.request_completion(
            messages=self._build_messages(),
            parameters=merged_params,
        )

        self.context.increment_cost(completion.cost)
        return completion

    def _build_messages(self) -> list[dict[str, Any]]:
        template_vars = {**copy.deepcopy(self.context.resolved_data)}
        messages = self.context.conversation_messages
        template_vars["messages"] = self._strip_inline_instructions(messages)
        template_vars["injected_prompt"] = self._build_injected_prompt(
            messages,
            template_vars.get("reinforcement_prompt"),
            template_vars.get("continue_prompt"),
        )
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        env.globals["load_base64"] = make_base64_loader(self.context.images_dir)
        with open(self.TEMPLATE_PATH) as file:
            template = env.from_string(file.read())
        rendered_str = template.render(template_vars)
        return yaml.safe_load(rendered_str)

    @staticmethod
    def _build_injected_prompt(
        messages: list,
        reinforcement_prompt: str | None,
        continue_prompt: str | None,
    ) -> str | None:
        parts = []
        if reinforcement_prompt:
            parts.append(reinforcement_prompt)
        if continue_prompt and messages and messages[-1].role == "assistant":
            parts.append(f"<instruct>{continue_prompt}</instruct>")
        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _strip_inline_instructions(messages: list) -> list:
        """Strip ## instructions from user messages that already have a response."""
        last_assistant_idx = -1
        for i, msg in enumerate(messages):
            if msg.role == "assistant":
                last_assistant_idx = i

        result = []
        for i, msg in enumerate(messages):
            if msg.role != "user" or not msg.content or "##" not in msg.content:
                result.append(msg)
                continue

            if i > last_assistant_idx:
                result.append(msg)
            else:
                body = msg.content.rsplit("##", 1)[0].rstrip()
                result.append(Message(msg.role, body, msg.image, msg.metadata))
        return result
