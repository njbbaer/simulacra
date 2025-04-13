import os
from pathlib import Path

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Conversation:
    def __init__(self, filepath):
        self._filepath = Path(filepath)
        self.load()

    def load(self):
        if os.path.exists(self._filepath):
            with open(self._filepath, "r") as file:
                data = yaml.load(file)
            self.cost = data.get("cost", 0.0)
            self.facts = data.get("facts", [])
            self.messages = data.get("messages", [])
        else:
            self.reset()

    def save(self):
        data_to_save = {
            "cost": self.cost,
            "facts": self.facts,
            "messages": self.messages,
        }
        with open(self._filepath, "w") as file:
            yaml.dump(data_to_save, file)

    def add_message(self, role, message, image_url=None, metadata=None):
        self.messages.append(
            {
                "role": role,
                "content": LiteralScalarString(message),
                **({"image_url": image_url} if image_url else {}),
                **({"metadata": metadata} if metadata else {}),
            }
        )

    def reset(self):
        self.cost = 0.0
        self.facts = []
        self.messages = []

    def add_fact(self, fact):
        self.facts.append(fact)

    def increment_cost(self, cost_increment):
        self.cost += cost_increment
