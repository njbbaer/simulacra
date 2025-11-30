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

    async def chat(
        self,
        user_input: str | None,
        image: str | None,
        documents: list[str] | None,
    ) -> str:
        self.context.load()
        if documents:
            for document in documents:
                user_input = self._append_document(user_input, document)
        if user_input or image:
            self.retry_stack.clear()
            if user_input:
                user_input = self._inject_instruction(user_input)
            self.context.add_message("user", user_input, image)
        self.context.save()
        completion = await ChatExecutor(self.context).execute()
        self.last_completion = completion
        scaffold = ResponseScaffold(completion.content, self.context.response_scaffold)
        self.context.add_message("assistant", scaffold.transformed_content)
        self.context.save()
        return scaffold.extract()

    async def new_conversation(self) -> None:
        self.retry_stack.clear()
        self.context.load()
        self.context.new_conversation()
        self.context.save()

    def reset_conversation(self) -> None:
        self.retry_stack.clear()
        self.context.load()
        self.context.reset_conversation()
        self.context.save()

    def add_conversation_fact(self, fact_text: str) -> None:
        self.context.load()
        self.context.add_conversation_fact(fact_text)
        self.context.save()

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
        self.context.load()
        removed_messages = []
        num_messages = len(self.context.conversation_messages)
        for _ in range(num_messages):
            message = self.context.conversation_messages.pop()
            removed_messages.append(message)
            if message.role == role:
                break
        self.context.save()
        return removed_messages

    def _restore_messages(self, messages: list) -> None:
        self.context.load()
        for message in reversed(messages):
            self.context.conversation_messages.append(message)
        self.context.save()

    def has_messages(self) -> bool:
        self.context.load()
        return len(self.context.conversation_messages) > 0

    def get_conversation_cost(self) -> float:
        self.context.load()
        return self.context.conversation_cost

    def sync_book(self, query: str) -> str:
        self.context.load()
        if not self.context.book_path:
            raise Exception("No book path set.")
        book = BookReader(self.context.book_path)
        start_idx = self.context.last_book_position or 0
        book_chunk, end_idx = book.next_chunk(query, start_idx=start_idx)
        message_content = f"<book_continuation>\n{book_chunk}\n</book_continuation>"
        self.retry_stack.clear()
        self.context.add_message("user", message_content, metadata={"end_idx": end_idx})
        self.context.save()
        return book_chunk

    @property
    def last_message_role(self) -> str:
        self.context.load()
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

        return textwrap.dedent(
            f"\n<document>\n\n{document}\n\n</document>\n\n---\n\n{text}"
        )
