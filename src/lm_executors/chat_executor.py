import os
from collections.abc import Callable
from typing import Any

import httpx
import jinja2
import yaml

from ..agent_sdk_client import fetch_agent_sdk_completion, is_agent_sdk_model
from ..api_client import fetch_completion
from ..chat_completion import ChatCompletion
from ..context import Context
from ..message import Message
from ..request_recorder import RequestRecorder
from ..utilities import make_base64_loader


class ChatExecutor:
    TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "chat_executor_template.j2")

    def __init__(
        self,
        context: Context,
        *,
        request_key: str,
        skip_injected_prompt: bool = False,
        extra_messages: list[Message] | None = None,
        include_images: bool = True,
    ) -> None:
        self.context = context
        self.request_key = request_key
        self._skip_injected_prompt = skip_injected_prompt
        self._extra_messages = extra_messages or []
        self._include_images = include_images

    async def execute(
        self,
        params: dict[str, Any] | None = None,
        on_retry: Callable[[], None] | None = None,
    ) -> ChatCompletion:
        body = {
            "messages": self._build_messages(),
            "session_id": self.context.session_id,
            **(self.context.api_params if params is None else params),
        }
        if is_agent_sdk_model(body["model"]):
            fetch = fetch_agent_sdk_completion
        else:
            fetch = fetch_completion
            if on_retry:
                fetch = fetch.retry_with(before_sleep=lambda _: on_retry())  # type: ignore[attr-defined]
        try:
            data = await fetch(body)
        except httpx.ReadTimeout as err:
            raise RuntimeError("Request timed out") from err

        RequestRecorder().record(body, data, self.request_key)
        completion = ChatCompletion(data)
        self.context.increment_cost(completion.cost)
        return completion

    def _build_messages(self) -> list[dict[str, Any]]:
        template_vars = dict(self.context.resolved_data)
        messages = [*self.context.conversation.messages, *self._extra_messages]
        messages = self._inject_inline_instructions(messages)
        if not self._include_images:
            messages = self._strip_images(messages)
        template_vars["messages"] = messages
        template_vars["injected_prompt"] = (
            None
            if self._skip_injected_prompt
            else self._build_injected_prompt(
                messages,
                template_vars.get("reinforcement_prompt"),
                template_vars.get("continue_prompt"),
            )
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
    def _strip_images(messages: list) -> list:
        """Replace image attachments with a text placeholder."""
        return [
            Message(msg.role, msg.content or "[image]", None, msg.metadata)
            if msg.image
            else msg
            for msg in messages
        ]

    @staticmethod
    def _inject_inline_instructions(messages: list) -> list:
        """Inject inline instructions from metadata into unresponded user messages."""
        last_assistant_idx = -1
        for i, msg in enumerate(messages):
            if msg.role == "assistant":
                last_assistant_idx = i

        result = []
        for i, msg in enumerate(messages):
            instruction = msg.metadata.get("inline_instruction")
            if instruction and i > last_assistant_idx:
                content = f"{msg.content or ''} [{instruction}]".strip()
                result.append(Message(msg.role, content, msg.image, msg.metadata))
            elif msg.content or msg.image:
                result.append(msg)
        return result
