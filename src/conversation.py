import re
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

    def format_as_transcript(self, character_name: str, user_name: str) -> str:
        """Render the messages as a screenplay, with thoughts quoted above the lines."""
        blocks = (
            _transcript_block(m, character_name, user_name) for m in self.messages
        )
        return "\n\n".join(block for block in blocks if block) + "\n"

    def add_message(
        self,
        role: str,
        message: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
        replacing: Message | None = None,
    ) -> None:
        """Append a message, keeping every attempt it replaces under `replaced`."""
        replaced = replacing.attempts if replacing else None
        self.messages.append(Message(role, message, image, metadata, replaced))

    def set_feedback(self, note: str) -> None:
        """Set the note on the last response or scene, replacing any earlier one."""
        last = self.messages[-1] if self.messages else None
        if not last or not last.generated:
            raise ValueError("No response to give feedback on")
        last.metadata["feedback"] = note

    def restore_replaced(self) -> None:
        """Swap the last message for the one it most recently replaced."""
        replaced = self.messages[-1].replaced if self.messages else None
        if not replaced:
            raise ValueError("No retry to undo")
        self.messages.pop()
        restored = replaced[-1]
        restored.replaced = replaced[:-1]
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


def _transcript_block(message: Message, character_name: str, user_name: str) -> str:
    """Scenes stand alone; other messages go under the speaker's name."""
    text = message.display_text
    if message.image:
        text = f"{text}\n\n[image: {message.image}]".strip()
    if message.metadata.get("scene"):
        return text
    tagged = re.finditer(r"<(\w+)>\s*(.*?)\s*</\1>", message.content or "", re.DOTALL)
    thoughts = [
        "\n".join(f"> {line}".rstrip() for line in match.group(2).splitlines())
        for match in tagged
    ]
    if not text and not thoughts:
        return ""
    speaker = character_name if message.role == "assistant" else user_name
    return "\n\n".join([speaker.upper(), *thoughts, *([text] if text else [])])
