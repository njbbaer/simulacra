from datetime import datetime
from pathlib import Path
from typing import Any

from .message import Message
from .yaml_config import yaml


class Conversation:
    """A conversation backed by a file, or held in memory only if no path is given."""

    def __init__(self, filepath: str | None = None) -> None:
        self._filepath = Path(filepath) if filepath else None
        self.load()

    def load(self) -> None:
        if self._filepath and self._filepath.exists():
            with open(self._filepath) as file:
                data = yaml.load(file)
            self.created_at = data.get("created_at")
            self.cost = data.get("cost", 0.0)
            self.plan_cost = data.get("plan_cost", 0.0)
            self.models = data.get("models", {})
            self.vars = data.get("vars", {})
            self.memories = data.get("memories", [])
            self.messages = [Message.from_dict(msg) for msg in data.get("messages", [])]
        else:
            self.reset()

    def save(self) -> None:
        if self._filepath is None:
            raise ValueError("Cannot save an in-memory conversation")
        data_to_save = {
            "created_at": self.created_at,
            "cost": self.cost,
            **({"plan_cost": self.plan_cost} if self.plan_cost else {}),
            **({"models": self.models} if self.models else {}),
            **({"vars": self.vars} if self.vars else {}),
            **({"memories": self.memories} if self.memories else {}),
            "messages": [msg.to_dict() for msg in self.messages],
        }
        with open(self._filepath, "w") as file:
            yaml.dump(data_to_save, file)

    def reset(self) -> None:
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cost = 0.0
        self.plan_cost = 0.0
        self.models = {}
        self.vars = {}
        self.memories = []
        self.messages = []

    def set_var(self, key: str, value: Any) -> None:
        self.vars[key] = value

    def format_as_memory(self, character_name: str) -> str:
        lines = []
        for msg in self.messages:
            if content := msg.display_text:
                role = "---" if msg.role == "user" else character_name.upper() + ":"
                lines.append(f"{role}\n\n{content}")
        return "\n\n".join(lines)

    def add_message(
        self,
        role: str,
        message: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
        replacing: Message | None = None,
    ) -> None:
        """Append a message, keeping any it replaces in its `replaced` metadata."""
        if replacing:
            earlier = replacing.metadata.get("replaced", [])
            previous = Message(
                replacing.role,
                replacing.content,
                replacing.image,
                {k: v for k, v in replacing.metadata.items() if k != "replaced"},
            )
            metadata = {**(metadata or {}), "replaced": [*earlier, previous.to_dict()]}
        self.messages.append(Message(role, message, image, metadata))

    def restore_replaced(self) -> None:
        """Swap the last message for the one it most recently replaced."""
        replaced = self.messages[-1].metadata.get("replaced") if self.messages else None
        if not replaced:
            raise ValueError("No retry to undo")
        self.messages.pop()
        restored = Message.from_dict(replaced[-1])
        if len(replaced) > 1:
            restored.metadata["replaced"] = replaced[:-1]
        self.messages.append(restored)

    def record_models(self, models: dict[str, str]) -> dict[str, str]:
        """Update the header, returning the keys that changed since last recorded."""
        current = dict(self.models)
        for msg in self.messages:
            current.update(msg.metadata.get("models", {}))
        changed = {}
        for key, value in models.items():
            if key not in self.models:
                self.models[key] = value
            elif current.get(key) != value:
                changed[key] = value
        return changed

    def increment_cost(self, cost: float, plan_cost: float = 0.0) -> None:
        self.cost += cost
        self.plan_cost += plan_cost
