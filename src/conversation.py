from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .message import Message
from .response_transform import strip_tags
from .yaml_config import yaml


class Conversation:
    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self.load()

    def load(self) -> None:
        if self._filepath.exists():
            with open(self._filepath) as file:
                data = yaml.load(file)
            self.created_at = data.get("created_at")
            self.cost = data.get("cost", 0.0)
            self.vars = data.get("vars", {})
            self.memories = data.get("memories", [])
            self.messages = [Message.from_dict(msg) for msg in data.get("messages", [])]
        else:
            self.reset()

    @classmethod
    def empty(cls) -> "Conversation":
        conv = cls.__new__(cls)
        conv.reset()
        return conv

    def save(self) -> None:
        data_to_save = {
            "created_at": self.created_at,
            "cost": self.cost,
            **({"vars": self.vars} if self.vars else {}),
            **(
                {"memories": [LiteralScalarString(m) for m in self.memories]}
                if self.memories
                else {}
            ),
            "messages": [msg.to_dict() for msg in self.messages],
        }
        with open(self._filepath, "w") as file:
            yaml.dump(data_to_save, file)

    def reset(self) -> None:
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cost = 0.0
        self.vars = {}
        self.memories = []
        self.messages = []

    def set_var(self, key: str, value: Any) -> None:
        self.vars[key] = value

    def format_as_memory(self, character_name: str) -> str:
        lines = []
        for msg in self.messages:
            if content := strip_tags(msg.content or ""):
                role = "OTHER" if msg.role == "user" else character_name.upper()
                lines.append(f"{role}:\n\n{content}")
        return "\n\n".join(lines)

    def add_message(
        self,
        role: str,
        message: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append(Message(role, message, image, metadata))

    def increment_cost(self, cost_increment: float) -> None:
        self.cost += cost_increment
