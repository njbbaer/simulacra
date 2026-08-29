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
    def __init__(
        self, path: str, overrides: dict | None = None, ephemeral: bool = False
    ) -> None:
        if os.path.isdir(path):
            dirname = os.path.basename(os.path.normpath(path))
            path = os.path.join(path, f"{dirname}.yml")
        self._filepath = path
        self._overrides = overrides or {}
        self._session_version = 0
        self._is_ephemeral = ephemeral
        if ephemeral:
            self._conversation = Conversation.empty()
        self.load()

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
        self._apply_extends()
        if self._overrides:
            self._data = merge_dicts(self._data, self._overrides)
        self._unresolved_data = self._data
        self._runtime_overrides: dict[str, Any] = {}
        self._state_data = self._load_state()
        if not self._is_ephemeral:
            self._load_conversation()
        self._rebuild()

    def with_overrides(self, overrides: dict[str, Any]) -> Context:
        """Return a copy with extra overrides applied. The copy shares the
        conversation and state, so its costs are added to this context."""
        clone = copy.copy(self)
        clone._runtime_overrides = merge_dicts(self._runtime_overrides, overrides)
        clone._rebuild()
        return clone

    def save(self) -> None:
        if self._is_ephemeral:
            return
        with open(self._state_filepath, "w") as f:
            yaml.dump(dict(self._state_data), f)
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

    def new_conversation(self, name: str | None = None) -> None:
        mgr = self._conversation_files
        filename = mgr.generate_filename(mgr.next_id(), name)
        self._set_conversation_file(filename)

    def compact_conversation(self) -> tuple[int, int]:
        old_size = sum(len(m.content or "") for m in self._conversation.messages)
        memory = self._conversation.format_as_memory(self.character_name)
        memories = [*self._conversation.memories, memory]
        current_name = self.conversation_name
        self.new_conversation(current_name)
        self._conversation.memories = memories
        return old_size, len(memory)

    def switch_conversation(self, identifier: str) -> tuple[int, str | None]:
        conv = self._conversation_files.find(identifier)
        self._set_conversation_file(conv.filename)
        return (conv.id, conv.name)

    def name_conversation(self, name: str) -> str:
        old_filename = os.path.basename(self._conversation_relpath)
        new_filename, sanitized = self._conversation_files.rename(old_filename, name)
        self._set_conversation_file(new_filename)
        return sanitized

    def increment_cost(self, cost: float) -> None:
        current = float(self._state_data.get("total_cost", 0))
        self._state_data["total_cost"] = current + cost
        self._conversation.increment_cost(cost)

    def set_conversation_var(self, key: str, value: Any) -> None:
        self._conversation.set_var(key, value)

    def apply_preset_overrides(self, key: str) -> None:
        presets = self.instruction_presets
        if key in presets:
            overrides = presets[key].overrides
            if overrides:
                self._runtime_overrides = merge_dicts(
                    self._runtime_overrides, overrides
                )
                self._rebuild()

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
    def is_ephemeral(self) -> bool:
        return self._is_ephemeral

    @property
    def trials_dir(self) -> str:
        return f"{self.dir}/trials"

    @property
    def character_name(self) -> str:
        return self._data["character_name"]

    @property
    def model(self) -> str:
        return self.api_params["model"]

    @property
    def conversation_file(self) -> str:
        return self._state_data["conversation_file"]

    @property
    def conversation_id(self) -> int:
        conv = self._current_conversation_file
        if conv:
            return conv.id
        raise ValueError(
            f"Invalid conversation file format: {self._conversation_relpath}"
        )

    @property
    def conversation_name(self) -> str | None:
        conv = self._current_conversation_file
        return conv.name if conv else None

    @property
    def book_path(self) -> str | None:
        path = self._data.get("book_path")
        if path:
            return os.path.join(self.dir, path)
        return None

    @property
    def book_postscript(self) -> str | None:
        return self._data.get("book_postscript")

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
    def scene_prompt(self) -> str | None:
        return self._data.get("scene_prompt")

    @property
    def post_process_prompt(self) -> str | None:
        return self._post_process.get("prompt")

    @property
    def post_process_params(self) -> dict[str, Any]:
        return merge_dicts(self.api_params, self._post_process.get("api_params", {}))

    @property
    def document_cleanup_prompt(self) -> str | None:
        return self._data.get("document_cleanup_prompt")

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

    def _load_state(self) -> dict[str, Any]:
        if os.path.exists(self._state_filepath):
            with open(self._state_filepath) as f:
                return yaml.load(f) or {}
        return {}

    def _load_conversation(self) -> None:
        os.makedirs(self.conversations_dir, exist_ok=True)
        if "conversation_file" not in self._state_data:
            mgr = self._conversation_files
            self._set_conversation_path(mgr.generate_filename(mgr.next_id()))
        full_path = os.path.join(self.dir, self._conversation_relpath)
        self._conversation = Conversation(full_path)

    def _set_conversation_path(self, filename: str) -> None:
        self._state_data["conversation_file"] = f"file://./conversations/{filename}"

    def _set_conversation_file(self, filename: str) -> None:
        self._set_conversation_path(filename)
        self._load_conversation()

    def _apply_extends(self) -> None:
        self._extend_dirs: list[str] = []
        self._data = self._extend_data(self._data, self.dir)

    def _extend_data(self, data: dict[str, Any], base_dir: str) -> dict[str, Any]:
        extends = data.pop("extends", None)
        if not extends:
            return data
        path = os.path.join(base_dir, extends)
        self._extend_dirs.append(os.path.dirname(path))
        with open(path) as f:
            base_data = self._extend_data(yaml.load(f), os.path.dirname(path))
        return merge_dicts(base_data, data)

    def _rebuild(self) -> None:
        """Layer runtime overrides onto the base data and resolve templates."""
        self._data = merge_dicts(self._unresolved_data, self._runtime_overrides)
        self._resolve_templates()

    def _resolve_templates(self) -> None:
        resolver = TemplateResolver(self.dir, self._search_dirs)
        extra_vars = {
            **self._state_data,
            "memories": self.conversation_memories,
            "vars": self.conversation_vars,
        }
        self._data = resolver.resolve(self._data, extra_vars)

    # Private properties

    @property
    def _post_process(self) -> dict[str, Any]:
        return self._data.get("post_process", {})

    @property
    def _state_filepath(self) -> str:
        base, _ = os.path.splitext(self._filepath)
        return f"{base}.state.yml"

    @property
    def _search_dirs(self) -> list[str]:
        dirs = [os.path.join(d, "content") for d in [self.dir, *self._extend_dirs]]
        shared_dir = self._data.get("shared_dir")
        if shared_dir:
            dirs.append(os.path.join(self.dir, shared_dir))
        return dirs

    @property
    def _context_name(self) -> str:
        return os.path.splitext(os.path.basename(self._filepath))[0]

    @property
    def _conversation_files(self) -> ConversationFiles:
        return ConversationFiles(self.conversations_dir, self._context_name)

    @property
    def _conversation_relpath(self) -> str:
        return self.conversation_file.replace("file://./", "")

    @property
    def _current_conversation_file(self):
        filename = os.path.basename(self._conversation_relpath)
        return self._conversation_files.parse_filename(filename)
