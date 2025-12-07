import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .message import Message
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
            self.facts = data.get("facts", [])
            self.memories = data.get("memories", [])
            self.messages = [Message.from_dict(msg) for msg in data.get("messages", [])]
        else:
            self.reset()

    def save(self) -> None:
        data_to_save = {
            "created_at": self.created_at,
            "cost": self.cost,
            "facts": self.facts,
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
        self.facts = []
        self.memories = []
        self.messages = []

    def format_as_memory(
        self, character_name: str, user_name: str, display_tag: str | None = None
    ) -> str:
        lines = []
        for msg in self.messages:
            content = self._extract_display_content(msg.content or "", display_tag)
            if content := content.strip():
                role = (
                    user_name.upper() if msg.role == "user" else character_name.upper()
                )
                lines.append(f"{role}:\n\n{content}")
        return "\n\n".join(lines)

    def _extract_display_content(self, text: str, display_tag: str | None) -> str:
        """Extract display tag content if present, otherwise strip all tags."""
        if display_tag:
            tag = re.escape(display_tag)
            match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.DOTALL)
            if match:
                return match.group(1).strip()
        return re.sub(r"<[^>]+>.*?</[^>]+>", "", text, flags=re.DOTALL)

    def add_message(
        self,
        role: str,
        message: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append(Message(role, message, image, metadata))

    def add_fact(self, fact: str) -> None:
        self.facts.append(fact)

    def increment_cost(self, cost_increment: float) -> None:
        self.cost += cost_increment
