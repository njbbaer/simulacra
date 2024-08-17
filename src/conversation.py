import os

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Conversation:
    def __init__(self, filepath):
        self._filepath = filepath

    def load(self):
        if os.path.exists(self._filepath):
            with open(self._filepath, "r") as file:
                self._data = yaml.load(file)
        else:
            self.reset()

    def save(self):
        with open(self._filepath, "w") as file:
            yaml.dump(self._data, file)

    def add_message(self, role, message, image_url=None):
        self.messages.append(
            {
                "role": role,
                "content": LiteralScalarString(message),
                **({"image_url": image_url} if image_url else {}),
            }
        )

    def reset(self):
        self._data = {
            "cost": 0,
            "facts": [],
            "messages": [],
        }

    def add_fact(self, fact):
        self._facts.append(fact)

    def increment_cost(self, new_cost):
        self._data["cost"] += new_cost

    @property
    def messages(self):
        return self._data["messages"]

    @property
    def cost(self):
        return self._data["cost"]

    @property
    def _facts(self):
        return self._data["facts"]
