import copy
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .conversation import Conversation
from .conversation_files import ConversationFiles
from .instruction_preset import InstructionPreset
from .message import Message
from .response_transform import Pattern
from .template_resolver import TemplateResolver
from .utilities import merge_dicts
from .yaml_config import yaml


class Session:
    def __init__(self, check_superseded: Callable[[], bool]):
        self._check_superseded = check_superseded

    @property
    def superseded(self) -> bool:
        return self._check_superseded()


class Context:
    def __init__(self, path: str) -> None:
        if os.path.isdir(path):
            dirname = os.path.basename(os.path.normpath(path))
            path = os.path.join(path, f"{dirname}.yml")
        self._filepath = path
        self._session_version = 0

    @contextmanager
    def session(self) -> Iterator[Session]:
        self._session_version += 1
        version = self._session_version
        self.load()
        try:
            yield Session(lambda: self._session_version != version)
        finally:
            if self._session_version == version:
                self.save()
            else:
                self.load()

    def load(self) -> None:
        with open(self._filepath) as file:
            self._raw_data = yaml.load(file)
        self._data = copy.deepcopy(self._raw_data)
        self._load_conversation()
        self._resolve_templates()
        self._apply_triggered_preset_overrides()

    def save(self) -> None:
        with open(self._filepath, "w") as file:
            yaml.dump(self._raw_data, file)
        self._conversation.save()

    def add_message(
        self,
        role: str,
        message: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._conversation.add_message(role, message, image, metadata)

    def reset_conversation(self) -> None:
        self._conversation.reset()

    def use_temp_conversation(self) -> None:
        self._conversation = Conversation.__new__(Conversation)
        self.reset_conversation()

    def new_conversation(self, name: str | None = None) -> None:
        mgr = self._conversation_files
        filename = mgr.generate_filename(mgr.next_id(), name)
        self._set_conversation_file(filename)

    def extend_conversation(self) -> None:
        memory = self._conversation.format_as_memory(
            self.character_name,
            self.user_name,
        )
        memories = [*self._conversation.memories, memory]
        current_name = self.conversation_name
        self.new_conversation(current_name)
        self._conversation.memories = memories

    def switch_conversation(self, identifier: str) -> tuple[int, str | None]:
        conv = self._conversation_files.find(identifier)
        self._set_conversation_file(conv.filename)
        return (conv.id, conv.name)

    def name_conversation(self, name: str) -> str:
        old_filename = os.path.basename(self.conversation_file.replace("file://./", ""))
        new_filename, sanitized = self._conversation_files.rename(old_filename, name)
        self._set_conversation_file(new_filename)
        return sanitized

    def increment_cost(self, cost: float) -> None:
        self._raw_data["total_cost"] = float(self._raw_data["total_cost"]) + cost
        self._conversation.increment_cost(cost)

    def set_conversation_var(self, key: str, value: Any) -> None:
        self._conversation.set_var(key, value)

    def apply_preset_overrides(self, key: str) -> None:
        presets = self.instruction_presets
        if key in presets:
            overrides = presets[key].overrides
            if overrides:
                self._data = merge_dicts(self._data, overrides)

    # Public properties

    @property
    def conversation_messages(self) -> list[Message]:
        return self._conversation.messages

    @property
    def conversation_cost(self) -> float:
        return self._conversation.cost

    @property
    def conversation_memories(self) -> list[str]:
        return self._conversation.memories

    @property
    def conversation_vars(self) -> dict[str, Any]:
        return self._conversation.vars

    @property
    def dir(self) -> str:
        return os.path.dirname(self._filepath)

    @property
    def conversations_dir(self) -> str:
        return f"{self.dir}/conversations"

    @property
    def images_dir(self) -> str:
        return f"{self.dir}/images"

    @property
    def character_name(self) -> str:
        return self._data["character_name"]

    @property
    def user_name(self) -> str:
        return self._data["user_name"]

    @property
    def model(self) -> str:
        return self.api_params["model"]

    @property
    def conversation_file(self) -> str:
        return self._data["conversation_file"]

    @property
    def conversation_id(self) -> int:
        conv = self._current_conversation_file
        if conv:
            return conv.id
        file_path = self.conversation_file.replace("file://./", "")
        raise ValueError(f"Invalid conversation file format: {file_path}")

    @property
    def conversation_name(self) -> str | None:
        conv = self._current_conversation_file
        return conv.name if conv else None

    @property
    def pricing(self) -> dict[str, Any] | None:
        return self._data.get("pricing", None)

    @property
    def book_path(self) -> str | None:
        path = self._data.get("book_path", None)
        if path:
            return os.path.join(self.dir, path)
        return None

    @property
    def last_book_position(self) -> int | None:
        for message in reversed(self.conversation_messages):
            metadata = message.metadata or {}
            if "end_idx" in metadata:
                return metadata["end_idx"]
        return None

    @property
    def response_patterns(self) -> list[Pattern]:
        raw = self._data.get("transform_patterns", [])
        return [
            Pattern(p["pattern"], p.get("replacement"), p.get("notify")) for p in raw
        ]

    @property
    def required_response_tags(self) -> set[str]:
        return set(self._data.get("require_tags", []))

    @property
    def experiment_variations(self) -> dict[str, Any]:
        return self._data.get("experiment_variations", {})

    @property
    def post_process_prompt(self) -> str | None:
        return self._data.get("post_process_prompt")

    @property
    def instruction_presets(self) -> dict[str, InstructionPreset]:
        return InstructionPreset.from_dict(self._data.get("instruction_presets", {}))

    @property
    def triggered_preset_keys(self) -> list[str]:
        return [
            msg.metadata["triggered_preset"]
            for msg in self._conversation.messages
            if msg.metadata and "triggered_preset" in msg.metadata
        ]

    @property
    def api_params(self) -> dict[str, Any]:
        return self._data.get("api_params", {})

    @property
    def resolved_data(self) -> dict[str, Any]:
        return self._data

    def _load_conversation(self) -> None:
        if "conversation_file" not in self._data:
            mgr = self._conversation_files
            filename = mgr.generate_filename(mgr.next_id())
            path = f"file://./conversations/{filename}"
            self._data["conversation_file"] = path
            self._raw_data["conversation_file"] = path
        os.makedirs(self.conversations_dir, exist_ok=True)
        file_path = self.conversation_file.replace("file://./", "")
        full_path = os.path.join(self.dir, file_path)
        self._conversation = Conversation(full_path)

    def _set_conversation_file(self, filename: str) -> None:
        path = f"file://./conversations/{filename}"
        self._raw_data["conversation_file"] = path
        self._data["conversation_file"] = path
        self._load_conversation()

    def _resolve_templates(self) -> None:
        resolver = TemplateResolver(self.dir)
        extra_vars = {
            "memories": self.conversation_memories,
            "vars": self.conversation_vars,
            "model": self.model,
        }
        self._data = resolver.resolve(self._data, extra_vars)

    def _apply_triggered_preset_overrides(self) -> None:
        for message in self._conversation.messages:
            if message.metadata and "triggered_preset" in message.metadata:
                self.apply_preset_overrides(message.metadata["triggered_preset"])

    # Private properties

    @property
    def _conversation_files(self) -> ConversationFiles:
        return ConversationFiles(self.conversations_dir, self.character_name)

    @property
    def _current_conversation_file(self):
        file_path = self.conversation_file.replace("file://./", "")
        filename = os.path.basename(file_path)
        return self._conversation_files.parse_filename(filename)
