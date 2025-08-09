import os
import textwrap
from typing import List, Optional, Type

from .book_reader import BookReader
from .chat_completion import ChatCompletion
from .context import Context
from .lm_executors import ChatExecutor as _ChatExecutor
from .lm_executors import ComparisonExecutor
from .response_scaffold import ResponseScaffold

ChatExecutor: Type[_ChatExecutor]
if os.getenv("ENABLE_COMPARISON_EXECUTOR") == "true":
    ChatExecutor = ComparisonExecutor
else:
    ChatExecutor = _ChatExecutor


class Simulacrum:
    def __init__(self, context_file: str) -> None:
        self.context = Context(context_file)
        self.last_completion: Optional[ChatCompletion] = None
        self.instruction_text: Optional[str] = None

    async def chat(
        self,
        user_input: Optional[str],
        image_url: Optional[str],
        documents: Optional[List[str]],
    ) -> str:
        self.context.load()
        if documents:
            for document in documents:
                user_input = self._append_document(user_input, document)
        if user_input:
            user_input = self._inject_instruction(user_input)
            self.context.add_message("user", user_input, image_url)
        self.context.save()
        completion = await ChatExecutor(self.context).execute()
        self.last_completion = completion
        scaffold = ResponseScaffold(completion.content, self.context.response_scaffold)
        self.context.add_message("assistant", scaffold.get_transformed_content())
        self.context.save()
        return scaffold.extract_output()

    async def new_conversation(self) -> None:
        self.context.load()
        self.context.new_conversation()
        self.context.save()

    def reset_conversation(self) -> None:
        self.context.load()
        self.context.reset_conversation()
        self.context.save()

    def add_conversation_fact(self, fact_text: str) -> None:
        self.context.load()
        self.context.add_conversation_fact(fact_text)
        self.context.save()

    def apply_instruction(self, instruction_text: str) -> None:
        self.instruction_text = instruction_text

    def undo_last_messages_by_role(self, role: str) -> None:
        self.context.load()
        num_messages = len(self.context.conversation_messages)
        for _ in range(num_messages):
            message = self.context.conversation_messages.pop()
            if message["role"] == role:
                break
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
        self.context.add_message("user", message_content, metadata={"end_idx": end_idx})
        self.context.save()
        return book_chunk

    @property
    def last_message_role(self) -> str:
        self.context.load()
        return self.context.conversation_messages[-1]["role"]

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
    def _append_document(text: Optional[str], document: str) -> Optional[str]:
        if not document:
            return text

        return textwrap.dedent(
            f"\nBEGIN DOCUMENT\n"
            f"\n{document}\n"
            f"\nEND DOCUMENT\n"
            f"\n---\n"
            f"\n{text}"
        )
