"""Search and read the conversation logs in a characters directory."""

import difflib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from itertools import zip_longest

from .conversation import Conversation
from .conversation_files import ConversationFiles
from .message import Message

LAYERS = ("text", "thoughts", "draft", "notes", "feedback", "replaced")
KINDS = ("user", "assistant", "scene")
EXCERPT_RADIUS = 100


@dataclass
class Log:
    character: str
    number: int
    path: str

    @property
    def id(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]

    @cached_property
    def conversation(self) -> Conversation:
        return Conversation(self.path)


@dataclass(frozen=True)
class Scope:
    """A character, one of its conversations, or one message, parsed from an ID."""

    character: str
    number: int | None = None
    index: int | None = None

    @classmethod
    def parse(cls, identifier: str) -> Scope:
        match = re.fullmatch(r"([a-z0-9]+)(?:_(\d+)(?:_\w+)?(?::(\d+))?)?", identifier)
        if not match:
            raise ValueError(
                f"Not a character, conversation, or message ID: {identifier}"
            )
        character, number, index = match.groups()
        return cls(
            character, int(number) if number else None, int(index) if index else None
        )


class History:
    def __init__(self, characters_dir: str) -> None:
        self._dir = characters_dir

    def characters(self) -> list[str]:
        return sorted(
            name
            for name in os.listdir(self._dir)
            if os.path.isdir(os.path.join(self._dir, name, "conversations"))
        )

    def logs(self, character: str, since: int = 0) -> list[Log]:
        """Return the character's logs numbered since or later, oldest first."""
        directory = os.path.join(self._dir, character, "conversations")
        if not os.path.isdir(directory):
            raise ValueError(f"No character named '{character}'")
        logs = [
            Log(character, conv.id, os.path.join(directory, conv.filename))
            for conv in ConversationFiles(directory, character).list()
            if conv.id >= since and "sync-conflict" not in conv.filename
        ]
        return sorted(logs, key=lambda log: log.number)

    def log(self, scope: Scope) -> Log:
        """Return the scope's conversation, or the character's latest one."""
        logs = self.logs(scope.character)
        if scope.number is None:
            if not logs:
                raise ValueError(f"{scope.character} has no conversations")
            return logs[-1]
        for log in logs:
            if log.number == scope.number:
                return log
        raise ValueError(f"No conversation {scope.character}_{scope.number}")

    def search(
        self,
        pattern: str | None,
        scopes: list[Scope] | None = None,
        *,
        layer: str = "text",
        kind: str | None = None,
        since: int = 0,
        ignore_case: bool = False,
    ) -> Iterator[tuple[Log, int, list[str]]]:
        """Yield each searched message with its matching lines, which may be none.

        Messages without that layer, or not of that kind, aren't searched. With no
        pattern, every value in the layer matches as one line."""
        regex = (
            re.compile(pattern, re.IGNORECASE if ignore_case else 0)
            if pattern
            else None
        )
        for log, indices in self._targets(scopes, since):
            for index, message in enumerate(log.conversation.messages):
                if indices is not None and index not in indices:
                    continue
                if kind and kind_of(message) != kind:
                    continue
                if values := layer_values(message, layer):
                    yield log, index, _matches(values, regex)

    def _targets(
        self, scopes: list[Scope] | None, since: int
    ) -> Iterator[tuple[Log, set[int] | None]]:
        if not scopes:
            scopes = [Scope(character) for character in self.characters()]
        for scope in scopes:
            if scope.number is None:
                for log in self.logs(scope.character, since):
                    yield log, None
            else:
                indices = None if scope.index is None else {scope.index}
                yield self.log(scope), indices


def kind_of(message: Message) -> str:
    return "scene" if message.metadata.get("scene") else message.role


def layer_values(message: Message, layer: str) -> list[str]:
    """Return the message's nonempty values in the layer."""
    return [value for value in _layer_values(message, layer) if value]


def _layer_values(message: Message, layer: str) -> list[str | None]:
    metadata = message.metadata
    match layer:
        case "text":
            return [message.display_text]
        case "thoughts":
            return [m.group(2) for m in _TAGGED.finditer(message.content or "")]
        case "draft":
            return list(metadata.get("drafts") or [metadata.get("draft")])
        case "notes":
            return [metadata.get("editor_notes")]
        case "feedback":
            return [attempt.metadata.get("feedback") for attempt in message.attempts]
        case "replaced":
            return [attempt.content for attempt in message.replaced]
    raise ValueError(f"Unknown layer: {layer}")


def render_conversation(log: Log) -> str:
    """Return the conversation's shown text, each message under its ID."""
    conversation = log.conversation
    header = [
        log.id,
        f"created {conversation.created_at}",
        f"cost ${conversation.cost:.2f} + plan ${conversation.plan_cost:.2f}",
        f"{len(conversation.messages)} messages",
    ]
    if conversation.memories:
        header.append(f"{len(conversation.memories)} memories")
    blocks = ["  ".join(header)]
    for index, message in enumerate(conversation.messages):
        blocks.append(_heading("──", log, index) + _body(message))
    return "\n\n".join(blocks) + "\n"


def render_turn(log: Log, index: int, context: int = 1) -> str:
    """Return the message in full, with its editing, earlier attempts, and context."""
    messages = log.conversation.messages
    if not 0 <= index < len(messages):
        raise ValueError(f"{log.id} has no message {index}")
    message = messages[index]
    blocks = []
    for before in range(max(0, index - context), index):
        blocks.append(_heading("──", log, before) + _body(messages[before]))
    blocks.append(_heading("══", log, index) + "\n" + (message.content or ""))
    if message.image:
        blocks[-1] += f"\n[image: {message.image}]"
    if feedback := message.metadata.get("feedback"):
        blocks.append(f"── feedback\n{feedback}")
    if extras := _extras(message):
        blocks.append("── metadata\n" + extras)
    if edit := _edit(message):
        blocks.append(edit)
    if notes := message.metadata.get("editor_notes"):
        blocks.append(f"── notes\n{notes}")
    for number, attempt in enumerate(message.replaced, 1):
        blocks.append(_attempt(attempt, number, len(message.replaced)))
    for after in range(index + 1, min(len(messages), index + 1 + context)):
        blocks.append(_heading("──", log, after) + _body(messages[after]))
    return "\n\n".join(blocks) + "\n"


def word_diff(old: str, new: str) -> str:
    """Return the changed paragraphs, marking cuts [-so-] and additions {+so+}."""
    old_paragraphs, new_paragraphs = _paragraphs(old), _paragraphs(new)
    matcher = difflib.SequenceMatcher(None, old_paragraphs, new_paragraphs)
    changed = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "equal":
            pairs = zip_longest(old_paragraphs[i1:i2], new_paragraphs[j1:j2])
            changed += [_word_diff(a or "", b or "") for a, b in pairs]
    return "\n\n".join(changed)


_TAGGED = re.compile(r"<(\w+)>\s*(.*?)\s*</\1>", re.DOTALL)
_SHOWN_ELSEWHERE = {"draft", "drafts", "editor_notes", "feedback", "scene"}


def _matches(values: list[str], regex: re.Pattern[str] | None) -> list[str]:
    if regex is None:
        return [" ".join(value.split()) for value in values]
    lines = []
    for value in values:
        for line in map(str.strip, value.splitlines()):
            if match := regex.search(line):
                lines.append(_excerpt(line, match.start()))
    return lines


def _excerpt(line: str, start: int) -> str:
    """Return the line within EXCERPT_RADIUS of start, trimmed to whole words."""
    begin = max(0, start - EXCERPT_RADIUS)
    end = min(len(line), start + EXCERPT_RADIUS)
    if begin and (space := line.find(" ", begin, start)) != -1:
        begin = space + 1
    if end < len(line) and (space := line.rfind(" ", start, end)) != -1:
        end = space
    return ("…" if begin else "") + line[begin:end] + ("…" if end < len(line) else "")


def _heading(rule: str, log: Log, index: int) -> str:
    message = log.conversation.messages[index]
    parts = [f"{rule} {log.id}:{index}", kind_of(message)]
    if message.replaced:
        parts.append(f"retried {len(message.replaced)}x")
    if any(attempt.metadata.get("feedback") for attempt in message.attempts):
        parts.append("feedback")
    return "  ".join(parts)


def _body(message: Message) -> str:
    lines = [message.display_text]
    if message.image:
        lines.append(f"[image: {message.image}]")
    if instruction := message.metadata.get("inline_instruction"):
        lines.append(f"[instruction: {instruction}]")
    text = "\n".join(line for line in lines if line)
    return f"\n{text}" if text else ""


def _extras(message: Message) -> str:
    return "\n".join(
        f"{key}: {value}"
        for key, value in message.metadata.items()
        if key not in _SHOWN_ELSEWHERE
    )


def _edit(message: Message) -> str | None:
    drafts = layer_values(message, "draft")
    if not drafts:
        return None
    title = "── editor" + (f" (draft 1 of {len(drafts)})" if len(drafts) > 1 else "")
    diff = word_diff(drafts[0], message.content or "")
    return f"{title}\n{diff or 'unchanged'}"


def _attempt(attempt: Message, number: int, total: int) -> str:
    lines = [f"── replaced {number} of {total}"]
    if feedback := attempt.metadata.get("feedback"):
        lines.append(f"feedback: {feedback}")
    lines.append(attempt.content or "")
    if notes := attempt.metadata.get("editor_notes"):
        lines.append(f"notes: {notes}")
    return "\n".join(lines)


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _word_diff(old: str, new: str) -> str:
    old_words, new_words = old.split(), new.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    parts = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            parts.append(" ".join(old_words[i1:i2]))
            continue
        if i2 > i1:
            parts.append(f"[-{' '.join(old_words[i1:i2])}-]")
        if j2 > j1:
            parts.append(f"{{+{' '.join(new_words[j1:j2])}+}}")
    return " ".join(parts)
