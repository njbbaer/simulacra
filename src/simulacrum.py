import asyncio
import re
import textwrap
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from . import notifications, trials
from .book_reader import BookReader
from .context import Context
from .document_cleaner import clean_document
from .instruction_preset import InstructionPreset
from .lm_executors import ChatExecutor
from .message import Message
from .request_recorder import RequestRecorder
from .response_transform import extract_tag, strip_tags, transform_response
from .utilities import parse_value

if TYPE_CHECKING:
    from .chat_completion import ChatCompletion

RESPONSE = trials.Stage("response")
POST_PROCESS = trials.Stage("post_process", scope="post_process")


@dataclass
class PendingInstruction:
    content: str
    preset_key: str | None = None


@dataclass
class StageResult:
    """One candidate's output, with the context and completion behind it."""

    content: str
    context: Context
    completion: ChatCompletion
    notes: str | None = None

    def as_candidate(self) -> dict[str, Any]:
        return {
            "content": self.content,
            **({"notes": self.notes} if self.notes else {}),
        }


@dataclass
class Generation:
    content: str
    display: str
    draft: str | None = None
    editor_notes: str | None = None
    trial_record: dict[str, Any] | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            **({"draft": self.draft} if self.draft else {}),
            **({"editor_notes": self.editor_notes} if self.editor_notes else {}),
            **({"trial": self.trial_record["id"]} if self.trial_record else {}),
        }


class Simulacrum:
    def __init__(
        self,
        context_file: str,
        ephemeral: bool = False,
        overrides: dict | None = None,
    ) -> None:
        self.context = Context(context_file, overrides=overrides, ephemeral=ephemeral)
        self.last_completion: ChatCompletion | None = None
        self._turn_cost: float = 0.0
        self._trial_log = trials.TrialLog(self.context)
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
            user_input, metadata = self._parse_user_input(user_input)
            if documents:
                user_input = await self._process_documents(user_input, documents)
            if user_input or image:
                self.retry_stack.clear()
                self.context.add_message("user", user_input, image, metadata)
            self.context.save()
            generation = await self._generate()
            self.context.add_message(
                "assistant", generation.content, metadata=generation.metadata
            )
            self._trial_log.write(generation.trial_record)
        return generation.display if not session.superseded else ""

    async def new_conversation(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            self.context.new_conversation()

    def compact_conversation(self) -> tuple[int, int]:
        self.retry_stack.clear()
        with self.context.session():
            return self.context.compact_conversation()

    def reset_conversation(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            self.context.reset_conversation()
        self._trial_log.delete()

    async def continue_conversation(self, instruction: str | None = None) -> str:
        self.retry_stack.clear()
        if instruction:
            self._set_inline_instruction(instruction)
        return await self.chat(None, None, None)

    async def scene(self, user_input: str | None = None) -> str:
        with self.context.session() as session:
            instructions = self.context.scene_prompt
            prompt = f"<instruct>\n{instructions}\n</instruct>"
            if user_input:
                prompt += f"\n{user_input}"
            self.context.save()
            generation = await self._generate_transient(prompt)
            metadata = {"scene": True, "scene_input": user_input}
            self.context.add_message("user", generation.content, metadata=metadata)
        return generation.display if not session.superseded else ""

    async def retry(self, instruction: str | None = None) -> str:
        self.context.load()
        msgs = self.context.conversation_messages
        if msgs and msgs[-1].metadata and msgs[-1].metadata.get("scene"):
            scene_input = msgs[-1].metadata.get("scene_input")
            removed = self._undo_last_messages_by_role("user")
            self.retry_stack.append(removed)
            return await self.scene(scene_input)
        with self.context.session():
            popped = self._pop_last_message("assistant")
            if popped:
                self.retry_stack.append([popped])
        if instruction:
            self._set_inline_instruction(instruction)
        return await self.chat(None, None, None)

    def undo(self) -> None:
        self.retry_stack.clear()
        with self.context.session():
            msgs = self.context.conversation_messages
            if not msgs:
                raise ValueError("No messages to undo")
            last_role = msgs.pop().role
            if last_role == "assistant":
                self._pop_last_message("user")
        self._trial_log.write()

    def undo_retry(self) -> None:
        if not self.retry_stack:
            raise ValueError("No retry to undo")
        with self.context.session():
            self._pop_last_message("assistant")
        self._restore_messages(self.retry_stack.pop())
        self._trial_log.write()

    def cancel_pending_request(self) -> None:
        if self._current_task:
            self._current_task.cancel()
            self._current_task = None

    def set_conversation_var(self, key: str, value: str) -> None:
        with self.context.session():
            self.context.set_conversation_var(key, parse_value(value))

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
            self.retry_stack.clear()
            self.context.add_message(
                "user", message_content, metadata={"end_idx": end_idx}
            )
            progress = end_idx / book.length if book.length else 0.0
        return book_chunk, progress

    def has_messages(self) -> bool:
        self.context.load()
        return bool(self.context.conversation_messages)

    def load_last_message(self) -> Message | None:
        self.context.load()
        return self.last_message

    @property
    def last_message(self) -> Message | None:
        msgs = self.context.conversation_messages
        return msgs[-1] if msgs else None

    @property
    def last_message_cost(self) -> float | None:
        """Cost of the last turn across every candidate of every stage."""
        if not self.last_completion:
            return None
        return self._turn_cost

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

    async def _generate(
        self,
        skip_required_tags: bool = False,
        skip_injected_prompt: bool = False,
        skip_post_process: bool = False,
    ) -> Generation:
        RequestRecorder().reset()
        self._turn_cost = 0.0

        response = await self._run_stage(
            RESPONSE,
            self.context,
            partial(
                self._respond,
                skip_injected_prompt=skip_injected_prompt,
                skip_required_tags=skip_required_tags,
            ),
        )
        self.last_completion = response.result.completion
        stages = {RESPONSE: response}

        result = response.result
        draft = None
        if not skip_post_process and result.context.post_process_prompt:
            draft = result.content
            edited = await self._run_stage(
                POST_PROCESS,
                result.context,
                partial(self._edit_draft, draft=draft),
            )
            stages[POST_PROCESS] = edited
            result = edited.result

        display = strip_tags(result.content)
        if not display:
            raise ValueError("No displayable content")
        return Generation(
            result.content, display, draft, result.notes, self._trial_record(stages)
        )

    async def _run_stage(
        self,
        stage: trials.Stage,
        context: Context,
        execute: Callable[[Context, str | None], Awaitable[StageResult]],
    ) -> trials.TrialRun[StageResult]:
        """Run one stage, charging every candidate it produced to the turn."""
        trial = await self._execute_with_cancellation(
            trials.run(context, stage, execute)
        )
        self._turn_cost += sum(r.completion.cost for r in trial.candidates.values())
        return trial

    async def _respond(
        self,
        context: Context,
        alias: str | None,
        *,
        skip_injected_prompt: bool,
        skip_required_tags: bool,
    ) -> StageResult:
        executor = ChatExecutor(
            context,
            request_key=RESPONSE.request_key(alias),
            skip_injected_prompt=skip_injected_prompt,
        )
        completion = await executor.execute()
        content = transform_response(
            completion.content,
            context.response_patterns,
            None if skip_required_tags else context.required_response_tags,
        )
        return StageResult(content, context, completion)

    async def _edit_draft(
        self, context: Context, alias: str | None, *, draft: str
    ) -> StageResult:
        """Re-generate the draft under the post-processing prompt."""
        instruction = f"<instruct>\n{context.post_process_prompt}\n</instruct>"
        executor = ChatExecutor(
            context,
            request_key=POST_PROCESS.request_key(alias),
            skip_injected_prompt=True,
            extra_messages=[
                Message("assistant", f"<draft>\n{draft}\n</draft>"),
                Message("user", instruction),
            ],
        )
        completion = await executor.execute(context.post_process_params)
        notes, content = extract_tag(completion.content, "assessment")
        content = transform_response(
            content,
            context.response_patterns,
            context.required_response_tags,
        )
        return StageResult(content, context, completion, notes)

    def _trial_record(
        self, stages: dict[trials.Stage, trials.TrialRun[StageResult]]
    ) -> dict[str, Any] | None:
        """Record every stage's candidates, or None if no stage ran a trial."""
        if not any(trial.selected for trial in stages.values()):
            return None
        record: dict[str, Any] = {"id": self._trial_log.next_id()}
        for stage, trial in stages.items():
            record[stage.name] = {
                **({"selected": trial.selected} if trial.selected else {}),
                "candidates": {
                    alias: result.as_candidate()
                    for alias, result in trial.candidates.items()
                },
            }
        return record

    async def _generate_transient(self, prompt: str) -> Generation:
        with self._temporary_message("user", prompt):
            return await self._generate(
                skip_required_tags=True,
                skip_injected_prompt=True,
                skip_post_process=True,
            )

    @contextmanager
    def _temporary_message(self, role: str, content: str) -> Iterator[None]:
        """Add a message for the duration of a request without persisting it."""
        messages = self.context.conversation_messages
        messages.append(Message(role, content))
        try:
            yield
        finally:
            messages.pop()

    async def _execute_with_cancellation[T](self, coro: Coroutine[Any, Any, T]) -> T:
        self._current_task = asyncio.create_task(coro)
        try:
            return await self._current_task
        finally:
            self._current_task = None

    def _pop_last_message(self, role: str) -> Message | None:
        msgs = self.context.conversation_messages
        if msgs and msgs[-1].role == role:
            return msgs.pop()
        return None

    def _undo_last_messages_by_role(self, role: str) -> list[Message]:
        with self.context.session():
            removed = []
            msgs = self.context.conversation_messages
            while msgs and msgs[-1].role != role:
                removed.append(msgs.pop())
            removed.append(msgs.pop())
            return removed

    def _restore_messages(self, messages: list[Message]) -> None:
        with self.context.session():
            for message in reversed(messages):
                self.context.conversation_messages.append(message)

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
        with self.context.session():
            msgs = self.context.conversation_messages
            if msgs and msgs[-1].role == "user":
                msgs[-1].metadata["inline_instruction"] = instruction
            else:
                self.context.add_message(
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
