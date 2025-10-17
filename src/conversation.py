import os
from pathlib import Path
from typing import Any, Dict, Optional

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Conversation:
    def __init__(self, filepath: str) -> None:
        self._filepath = Path(filepath)
        self.load()

    def load(self) -> None:
        if os.path.exists(self._filepath):
            with open(self._filepath, "r") as file:
                data = yaml.load(file)
            self.cost = data.get("cost", 0.0)
            self.facts = data.get("facts", [])
            self.messages = data.get("messages", [])
        else:
            self.reset()

    def save(self) -> None:
        data_to_save = {
            "cost": self.cost,
            "facts": self.facts,
            "messages": self.messages,
        }
        with open(self._filepath, "w") as file:
            yaml.dump(data_to_save, file)

    def add_message(
        self,
        role: str,
        message: str,
        image: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.messages.append(
            {
                "role": role,
                "content": LiteralScalarString(message),
                **({"image": image} if image else {}),
                **({"metadata": metadata} if metadata else {}),
            }
        )

    def reset(self) -> None:
        self.cost = 0.0
        self.facts = []
        self.messages = []

    def add_fact(self, fact: str) -> None:
        self.facts.append(fact)

    def increment_cost(self, cost_increment: float) -> None:
        self.cost += cost_increment
