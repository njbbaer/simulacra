import copy
import os
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .conversation import Conversation
from .instruction_preset import InstructionPreset
from .message import Message
from .scaffold_config import ScaffoldConfig
from .template_resolver import TemplateResolver
from .yaml_config import yaml


class Session:
    def __init__(self, check_superseded: Callable[[], bool]):
        self._check_superseded = check_superseded

    @property
    def superseded(self) -> bool:
        return self._check_superseded()


class Context:
    def __init__(self, filepath: str) -> None:
        self._filepath = filepath
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

    def new_conversation(self) -> None:
        next_id = self._next_conversation_id()
        self._raw_data["conversation_file"] = self._generate_conversation_path(next_id)
        self._data["conversation_file"] = self._raw_data["conversation_file"]
        self._load_conversation()

    def extend_conversation(self) -> None:
        memory = self._conversation.format_as_memory(
            self.character_name,
            self.user_name,
        )
        memories = [*self._conversation.memories, memory]
        self.new_conversation()
        self._conversation.memories = memories

    def increment_cost(self, cost: float) -> None:
        self._raw_data["total_cost"] = float(self._raw_data["total_cost"]) + cost
        self._conversation.increment_cost(cost)

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

    def set_conversation_var(self, key: str, value: Any) -> None:
        self._conversation.set_var(key, value)

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
        file_path = self.conversation_file.replace("file://./", "")
        filename = os.path.basename(file_path)
        match = re.match(rf"^{self.character_name.lower()}_(\d+)\.yml$", filename)
        if match:
            return int(match.group(1))
        raise ValueError(f"Invalid conversation file format: {file_path}")

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
    def response_scaffold(self) -> ScaffoldConfig:
        scaffold_config_dict = self._data.get("response_scaffold", {})
        return ScaffoldConfig.from_dict(scaffold_config_dict)

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
    def api_params(self) -> dict[str, Any]:
        return self._data.get("api_params", {})

    @property
    def resolved_data(self) -> dict[str, Any]:
        return self._data

    def _load_conversation(self) -> None:
        if "conversation_file" not in self._data:
            next_id = self._next_conversation_id()
            path = self._generate_conversation_path(next_id)
            self._data["conversation_file"] = path
            self._raw_data["conversation_file"] = path
        os.makedirs(self.conversations_dir, exist_ok=True)
        file_path = self.conversation_file.replace("file://./", "")
        full_path = os.path.join(self.dir, file_path)
        self._conversation = Conversation(full_path)

    def _generate_conversation_path(self, conversation_id: int) -> str:
        return f"file://./conversations/{self.character_name.lower()}_{conversation_id}.yml"

    def _next_conversation_id(self) -> int:
        max_id = max(
            (
                int(os.path.splitext(file)[0].split("_")[1])
                for file in os.listdir(self.conversations_dir)
                if re.match(rf"^{self.character_name.lower()}_\d+\.yml$", file)
            ),
            default=0,
        )
        return max_id + 1

    def _resolve_templates(self) -> None:
        resolver = TemplateResolver(self.dir)
        extra_vars = {
            "memories": self.conversation_memories,
            "vars": self.conversation_vars,
            "model": self.model,
        }
        self._data = resolver.resolve(self._data, extra_vars)
