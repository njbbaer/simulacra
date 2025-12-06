import asyncio
import os
import textwrap
from typing import TYPE_CHECKING

from .book_reader import BookReader
from .context import Context
from .lm_executors import ChatExecutor as _ChatExecutor
from .lm_executors import ExperimentExecutor
from .response_scaffold import ResponseScaffold

if TYPE_CHECKING:
    from .chat_completion import ChatCompletion
    from .message import Message

ChatExecutor: type[_ChatExecutor]
if os.getenv("ENABLE_EXPERIMENT_EXECUTOR") == "true":
    ChatExecutor = ExperimentExecutor
else:
    ChatExecutor = _ChatExecutor


class Simulacrum:
    def __init__(self, context_file: str) -> None:
        self.context = Context(context_file)
        self.last_completion: ChatCompletion | None = None
        self.instruction_text: str | None = None
        self.retry_stack: list[list[Message]] = []
        self._current_task: asyncio.Task | None = None

    def cancel_pending_request(self) -> None:
        if self._current_task:
            self._current_task.cancel()
            self._current_task = None

    async def chat(
        self,
        user_input: str | None,
        image: str | None,
        documents: list[str] | None,
    ) -> str:
        with self.context.session():
            if documents:
                for document in documents:
                    user_input = self._append_document(user_input, document)
            if user_input or image:
                self.retry_stack.clear()
                if user_input:
                    user_input = self._inject_instruction(user_input)
                self.context.add_message("user", user_input, image)
            self.context.save()
            completion = await self._execute_with_cancellation(
                ChatExecutor(self.context).execute()
            )
            self.last_completion = completion
            scaffold = ResponseScaffold(
                completion.content, self.context.response_scaffold
            )
            self.context.add_message("assistant", scaffold.transformed_content)
        return scaffold.display

    async def _execute_with_cancellation(self, coro) -> "ChatCompletion":
        self._current_task = asyncio.create_task(coro)
        try:
            return await self._current_task
        finally:
            self._current_task = None

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

    def add_conversation_fact(self, fact_text: str) -> None:
        with self.context.session():
            self.context.add_conversation_fact(fact_text)

    def apply_instruction(self, instruction_text: str) -> None:
        self.instruction_text = instruction_text

    def undo(self) -> None:
        self.retry_stack.clear()
        self._undo_last_messages_by_role("user")

    async def retry(self) -> str:
        if self.last_message_role == "assistant":
            removed_messages = self._undo_last_messages_by_role("assistant")
            self.retry_stack.append(removed_messages)
        return await self.chat(None, None, None)

    async def continue_conversation(self) -> str:
        return await self.chat(None, None, None)

    def undo_retry(self) -> bool:
        if not self.retry_stack:
            return False
        if self.last_message_role == "assistant":
            self._undo_last_messages_by_role("assistant")
        messages_to_restore = self.retry_stack.pop()
        self._restore_messages(messages_to_restore)
        return True

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

    def has_messages(self) -> bool:
        self.context.load()
        return len(self.context.conversation_messages) > 0

    def get_conversation_cost(self) -> float:
        self.context.load()
        return self.context.conversation_cost

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

    @property
    def last_message_role(self) -> str:
        self.context.load()
        if not self.context.conversation_messages:
            raise ValueError("No messages in conversation")
        return self.context.conversation_messages[-1].role

    def _inject_instruction(self, text: str) -> str:
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

    @staticmethod
    def _append_document(text: str | None, document: str) -> str | None:
        if not document:
            return text

        content = f"<document>\n{document}\n</document>"
        if text:
            content += f"\n\n---\n\n{text}"
        return textwrap.dedent(content)
