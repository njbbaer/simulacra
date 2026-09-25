import re
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import notifications, trials
from .book_reader import BookReader
from .context import Context, Session
from .document_cleaner import clean_document
from .generator import Generation, Generator
from .instruction_preset import InstructionPreset
from .message import Message
from .telemetry import Telemetry
from .utilities import parse_value

if TYPE_CHECKING:
    from .turn_stats import TurnStats


@dataclass
class PendingInstruction:
    content: str
    preset_key: str | None = None


class Simulacrum:
    def __init__(
        self,
        context_file: str,
        ephemeral: bool = False,
        overrides: dict | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.context = Context(context_file, overrides=overrides, ephemeral=ephemeral)
        self._trial_log = trials.TrialLog(self.context)
        self._generator = Generator(self._trial_log, telemetry or Telemetry())
        self._pending_instruction: PendingInstruction | None = None

    async def chat(
        self, user_input: str | None, image: str | None, documents: list[str] | None
    ) -> str:
        self._ensure_idle()
        with self.context.session() as session:
            user_input, metadata = self._parse_user_input(user_input)
            if documents:
                user_input = await self._process_documents(user_input, documents)
            if user_input or image:
                self.context.conversation.add_message(
                    "user", user_input, image, metadata
                )
            self.context.save()
            return await self._reply(session, "chat")

    async def new_conversation(self) -> None:
        with self.context.session():
            self.context.new_conversation()

    def compact_conversation(self) -> tuple[int, int]:
        with self.context.session():
            return self.context.compact_conversation()

    def reset_conversation(self) -> None:
        with self.context.session():
            self.context.conversation.reset()
        self._trial_log.delete()

    async def continue_conversation(self, instruction: str | None = None) -> str:
        self._ensure_idle()
        with self.context.session() as session:
            if instruction:
                self._set_inline_instruction(instruction)
            self.context.save()
            return await self._reply(session, "continue")

    async def scene(self, user_input: str | None = None) -> str:
        self._ensure_idle()
        with self.context.session() as session:
            return await self._narrate(session, user_input)

    async def retry(self, instruction: str | None = None) -> str:
        """Regenerate the last response or scene, keeping the old one to undo to."""
        self._ensure_idle()
        with self.context.session() as session:
            messages = self.context.conversation.messages
            last = self.last_message
            replaced = None
            if last and (last.role == "assistant" or last.metadata.get("scene")):
                replaced = messages.pop()
            try:
                if replaced and replaced.metadata.get("scene"):
                    scene_input = replaced.metadata.get("scene_input")
                    return await self._narrate(session, scene_input, replaced)
                if instruction:
                    self._set_inline_instruction(instruction)
                return await self._reply(session, "retry", replaced)
            except BaseException:
                # The pop was never saved, so this leaves the file unchanged
                if replaced:
                    messages.append(replaced)
                raise

    def undo(self) -> None:
        with self.context.session():
            msgs = self.context.conversation.messages
            if not msgs:
                raise ValueError("No messages to undo")
            last_role = msgs.pop().role
            if last_role == "assistant":
                self._pop_last_message("user")
        self._trial_log.write()

    def undo_retry(self) -> None:
        self._ensure_idle()
        with self.context.session():
            self.context.conversation.restore_replaced()
        self._trial_log.write()

    def cancel_pending_request(self) -> bool:
        return self._generator.cancel()

    def set_conversation_var(self, key: str, value: str) -> None:
        with self.context.session():
            self.context.conversation.set_var(key, parse_value(value))

    def apply_preset(self, key: str) -> str | None:
        """Queue a named preset, returning its display name, or None if unknown."""
        self.context.load()
        preset = self.context.instruction_presets.get(key)
        if not preset:
            return None
        self._pending_instruction = PendingInstruction(preset.content, key)
        return preset.name or key

    def apply_instruction(self, text: str) -> None:
        self._pending_instruction = PendingInstruction(text)

    def sync_book(self, query: str) -> tuple[str, float]:
        with self.context.session():
            if not self.context.book_path:
                raise ValueError("No book path set.")
            book = BookReader(self.context.book_path)
            start_idx = self.context.last_book_position or 0
            book_chunk, end_idx = book.next_chunk(query, start_idx=start_idx)
            message_content = f"<book_content>\n{book_chunk}\n</book_content>"
            if postscript := self.context.book_postscript:
                message_content += f"\n\n{postscript}"
            self.context.conversation.add_message(
                "user", message_content, metadata={"end_idx": end_idx}
            )
            progress = end_idx / book.length if book.length else 0.0
        return book_chunk, progress

    def has_messages(self) -> bool:
        self.context.load()
        return bool(self.context.conversation.messages)

    def load_last_message(self) -> Message | None:
        self.context.load()
        return self.last_message

    @property
    def last_message(self) -> Message | None:
        msgs = self.context.conversation.messages
        return msgs[-1] if msgs else None

    @property
    def last_turn(self) -> TurnStats | None:
        return self._generator.last_turn

    @property
    def last_message_cost(self) -> float | None:
        """Cost of the last turn across every request of every stage."""
        if not self.last_turn or not self.last_turn.requests:
            return None
        return self.last_turn.cost

    def get_conversation_cost(self) -> float:
        self.context.load()
        return self.context.conversation.cost

    def switch_conversation(self, identifier: str) -> tuple[int, str | None]:
        with self.context.session():
            return self.context.switch_conversation(identifier)

    def name_conversation(self, name: str) -> str:
        with self.context.session():
            return self.context.name_conversation(name)

    def _ensure_idle(self) -> None:
        if self._generator.busy:
            raise ValueError("Still responding")

    async def _reply(
        self, session: Session, action: str, replacing: Message | None = None
    ) -> str:
        generation = await self._generate(action)
        return self._record(session, "assistant", generation, replacing=replacing)

    async def _narrate(
        self,
        session: Session,
        user_input: str | None,
        replacing: Message | None = None,
    ) -> str:
        prompt = f"<instruct>\n{self.context.scene_prompt}\n</instruct>"
        if user_input:
            prompt += f"\n{user_input}"
        with self._temporary_message("user", prompt):
            generation = await self._generate(
                "scene",
                skip_required_tags=True,
                skip_injected_prompt=True,
                skip_post_process=True,
            )
        metadata = {"scene": True, "scene_input": user_input}
        return self._record(session, "user", generation, metadata, replacing)

    def _record(
        self,
        session: Session,
        role: str,
        generation: Generation,
        metadata: dict[str, Any] | None = None,
        replacing: Message | None = None,
    ) -> str:
        """Append the message and trial, returning display text or "" if superseded."""
        if session.superseded:
            return ""
        conversation = self.context.conversation
        markers = conversation.record_models(generation.models)
        conversation.add_message(
            role,
            generation.content,
            metadata={
                **(metadata or {}),
                **({"models": markers} if markers else {}),
                **generation.metadata,
            },
            replacing=replacing,
        )
        self._trial_log.write(generation.trial_record)
        return generation.display

    async def _generate(self, action: str, **options: bool) -> Generation:
        return await self._generator.generate(self.context, action=action, **options)

    @contextmanager
    def _temporary_message(self, role: str, content: str) -> Iterator[None]:
        """Add a message for the duration of a request without persisting it."""
        messages = self.context.conversation.messages
        messages.append(Message(role, content))
        try:
            yield
        finally:
            messages.pop()

    def _pop_last_message(self, role: str) -> Message | None:
        msgs = self.context.conversation.messages
        if msgs and msgs[-1].role == role:
            return msgs.pop()
        return None

    @staticmethod
    def _extract_inline_instruction(text: str) -> tuple[str, str | None]:
        match = re.search(r"\s*\[([^\]]+)\]$", text)
        if not match:
            return text, None
        return text[: match.start()], match.group(1)

    def _parse_user_input(self, text: str | None) -> tuple[str | None, dict]:
        metadata: dict[str, str] = {}
        if not text:
            return text, metadata
        text, triggered_key = self._apply_pending_preset(text)
        text, instruction = self._extract_inline_instruction(text)
        if triggered_key:
            metadata["triggered_preset"] = triggered_key
        if instruction:
            metadata["inline_instruction"] = instruction
        return text, metadata

    def _set_inline_instruction(self, instruction: str) -> None:
        msgs = self.context.conversation.messages
        if msgs and msgs[-1].role == "user":
            msgs[-1].metadata["inline_instruction"] = instruction
        else:
            self.context.conversation.add_message(
                "user", None, metadata={"inline_instruction": instruction}
            )

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

    async def _process_documents(
        self, text: str | None, documents: list[str]
    ) -> str | None:
        prompt = self.context.document_cleanup_prompt
        for document in documents:
            document = await clean_document(document, prompt)
            tokens = len(document) // 4
            notifications.send(f"Document added: {tokens:,} tokens")
            text = self._append_document(text, document)
        return text

    @staticmethod
    def _append_document(text: str | None, document: str) -> str | None:
        if not document:
            return text

        content = f"<document>\n{document}\n</document>"
        if text:
            content += f"\n\n---\n\n{text}"
        return textwrap.dedent(content)
