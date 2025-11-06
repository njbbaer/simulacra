import os
from pathlib import Path
from typing import Any

from .message import Message
from .yaml_config import yaml


class Conversation:
    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self.load()

    def load(self) -> None:
        if os.path.exists(self._filepath):
            with open(self._filepath) as file:
                data = yaml.load(file)
            self.cost = data.get("cost", 0.0)
            self.facts = data.get("facts", [])
            self.messages = [Message.from_dict(msg) for msg in data.get("messages", [])]
        else:
            self.reset()

    def save(self) -> None:
        data_to_save = {
            "cost": self.cost,
            "facts": self.facts,
            "messages": [msg.to_dict() for msg in self.messages],
        }
        with open(self._filepath, "w") as file:
            yaml.dump(data_to_save, file)

    def add_message(
        self,
        role: str,
        message: str,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append(Message(role, message, image, metadata))

    def reset(self) -> None:
        self.cost = 0.0
        self.facts = []
        self.messages = []

    def add_fact(self, fact: str) -> None:
        self.facts.append(fact)

    def increment_cost(self, cost_increment: float) -> None:
        self.cost += cost_increment
