import asyncio
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import notifications
from .book_reader import BookReader
from .context import Context
from .instruction_preset import InstructionPreset
from .lm_executors import ChatExecutor, ExperimentExecutor
from .post_processor import post_process_response
from .response_scaffold import ResponseScaffold
from .utilities import parse_value

if TYPE_CHECKING:
    from .chat_completion import ChatCompletion
    from .message import Message


@dataclass
class PendingInstruction:
    content: str
    preset_key: str | None = None


class Simulacrum:
    def __init__(self, context_file: str) -> None:
        self.context = Context(context_file)
        self.last_completion: ChatCompletion | None = None
        self.experiment_mode: bool = False
        self._pending_instruction: PendingInstruction | None = None
        self.retry_stack: list[list[Message]] = []
        self._current_task: asyncio.Task | None = None

    async def chat(
        self,
        user_input: str | None,
        image: str | None,
        documents: list[str] | None,
    ) -> str:
        with self.context.session() as session:
            if documents:
                for document in documents:
                    user_input = self._append_document(user_input, document)
            if user_input or image:
                self.retry_stack.clear()
                if user_input:
                    user_input, triggered_key = self._apply_pending_preset(user_input)
                    metadata = (
                        {"triggered_preset": triggered_key} if triggered_key else None
                    )
                else:
                    metadata = None
                self.context.add_message("user", user_input, image, metadata)
            self.context.save()
            executor_cls = ExperimentExecutor if self.experiment_mode else ChatExecutor
            completion = await self._execute_with_cancellation(
                executor_cls(self.context).execute()
            )
            self.last_completion = completion
            scaffold = ResponseScaffold(
                completion.content, self.context.response_scaffold
            )
            scaffold.transformed_content = await post_process_response(
                scaffold.transformed_content,
                self.context.post_process_prompt,
            )
            self.context.add_message("assistant", scaffold.transformed_content)
        return scaffold.display if not session.superseded else ""

    async def new_conversation(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            self.context.new_conversation()

    async def extend_conversation(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            self.context.extend_conversation()

    def reset_conversation(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            self.context.reset_conversation()

    async def continue_conversation(self) -> str:
        return await self.chat(None, None, None)

    async def retry(self) -> str:
        if self.last_message_role == "assistant":
            removed_messages = self._undo_last_messages_by_role("assistant")
            self.retry_stack.append(removed_messages)
        return await self.chat(None, None, None)

    def undo(self) -> None:
        self.retry_stack.clear()
        self._undo_last_messages_by_role("user")

    def undo_retry(self) -> bool:
        if not self.retry_stack:
            return False
        if self.last_message_role == "assistant":
            self._undo_last_messages_by_role("assistant")
        messages_to_restore = self.retry_stack.pop()
        self._restore_messages(messages_to_restore)
        return True

    def cancel_pending_request(self) -> None:
        if self._current_task:
            self._current_task.cancel()
            self._current_task = None

    def set_conversation_var(self, key: str, value: str) -> None:
        with self.context.session():
            self.context.set_conversation_var(key, parse_value(value))

    def apply_instruction(self, text: str) -> str | None:
        self.context.load()
        presets = self.context.instruction_presets
        if text in presets:
            preset = presets[text]
            self._pending_instruction = PendingInstruction(preset.content, text)
            return preset.name or text
        self._pending_instruction = PendingInstruction(text)
        return None

    def sync_book(self, query: str) -> str:
        with self.context.session():
            if not self.context.book_path:
                raise Exception("No book path set.")
            book = BookReader(self.context.book_path)
            start_idx = self.context.last_book_position or 0
            book_chunk, end_idx = book.next_chunk(query, start_idx=start_idx)
            message_content = f"<book_continuation>\n{book_chunk}\n</book_continuation>"
            self.retry_stack.clear()
            self.context.add_message(
                "user", message_content, metadata={"end_idx": end_idx}
            )
        return book_chunk

    def has_messages(self) -> bool:
        self.context.load()
        return len(self.context.conversation_messages) > 0

    def get_conversation_cost(self) -> float:
        self.context.load()
        return self.context.conversation_cost

    def switch_conversation(self, identifier: str) -> tuple[int, str | None]:
        self.retry_stack.clear()
        with self.context.session():
            return self.context.switch_conversation(identifier)

    def name_conversation(self, name: str) -> str:
        with self.context.session():
            return self.context.name_conversation(name)

    @property
    def last_message_role(self) -> str:
        self.context.load()
        if not self.context.conversation_messages:
            raise ValueError("No messages in conversation")
        return self.context.conversation_messages[-1].role

    async def _execute_with_cancellation(self, coro) -> "ChatCompletion":
        self._current_task = asyncio.create_task(coro)
        try:
            return await self._current_task
        finally:
            self._current_task = None

    def _undo_last_messages_by_role(self, role: str) -> list:
        with self.context.session():
            removed_messages = []
            num_messages = len(self.context.conversation_messages)
            for _ in range(num_messages):
                message = self.context.conversation_messages.pop()
                removed_messages.append(message)
                if message.role == role:
                    break
        return removed_messages

    def _restore_messages(self, messages: list) -> None:
        with self.context.session():
            for message in reversed(messages):
                self.context.conversation_messages.append(message)

    def _apply_pending_preset(self, text: str) -> tuple[str, str | None]:
        instruction: str | None = None
        preset_key: str | None = None

        if self._pending_instruction:
            instruction = self._pending_instruction.content
            preset_key = self._pending_instruction.preset_key
            self._pending_instruction = None
        else:
            match = InstructionPreset.find_match(
                self.context.instruction_presets,
                text,
                self.context.triggered_preset_keys,
            )
            if match:
                preset_key, preset = match
                instruction = preset.content
                notifications.send(f"Preset '{preset.name or preset_key}' triggered")

        if preset_key:
            self.context.apply_preset_overrides(preset_key)

        if instruction:
            text = f"{text}\n\n<instruct>\n{instruction}\n</instruct>"

        return text, preset_key

    @staticmethod
    def _append_document(text: str | None, document: str) -> str | None:
        if not document:
            return text

        content = f"<document>\n{document}\n</document>"
        if text:
            content += f"\n\n---\n\n{text}"
        return textwrap.dedent(content)
