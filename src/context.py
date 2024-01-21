import os
from datetime import datetime

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Context:
    def __init__(self, context_filepath):
        self.context_filepath = context_filepath
        self.load()

    def load(self):
        with open(self.context_filepath, "r") as file:
            self.data = yaml.load(file)
        self._initialize_conversation_data()

    def save(self):
        with open(self.context_filepath, "w") as file:
            yaml.dump(self.data, file)

    def add_message(self, role, message, image_url=None):
        self.current_conversation["messages"].append(
            {
                "role": role,
                "content": LiteralScalarString(message),
                **({"image_url": image_url} if image_url else {}),
            }
        )

    def clear_messages(self, n=None):
        self.current_conversation["messages"] = self.current_messages[:-n]

    def reset_current_conversation(self):
        self.current_conversation["cost"] = 0
        self.current_conversation["facts"] = []
        self.current_conversation["messages"] = []

    def new_conversation(self):
        self.data["conversations"].append(
            {
                "name": get_current_timestamp_string(),
                "cost": 0,
                "facts": [],
                "messages": [],
            }
        )

    def get_name(self, role):
        return self.data["names"][role]

    def add_cost(self, new_cost):
        self.data["total_cost"] = self.total_cost + new_cost
        self.current_conversation["cost"] = self.current_conversation_cost + new_cost

    def add_conversation_fact(self, fact):
        self.current_conversation["facts"].append(fact)

    @property
    def current_conversation(self):
        return self.data["conversations"][-1]

    @property
    def vars(self):
        return self.data["vars"]

    @property
    def parameters(self):
        return self.data.get("parameters") or {}

    @property
    def current_messages(self):
        return self.current_conversation["messages"]

    @property
    def current_conversation_cost(self):
        return self.current_conversation["cost"]

    @property
    def current_conversation_facts(self):
        return self.vars.get("default_facts", []) + self.current_conversation["facts"]

    @property
    def total_cost(self):
        return self.data["total_cost"]

    @property
    def image_prompts(self):
        return self.vars.get("image_prompts", [])

    @property
    def file_dir(self):
        return os.path.dirname(self.context_filepath)

    def _initialize_conversation_data(self):
        self.data.setdefault("total_cost", 0)
        self.data.setdefault("conversations", [{}])
        current_conversation = self.data["conversations"][-1]
        current_conversation.setdefault("name", get_current_timestamp_string())
        current_conversation.setdefault("cost", 0)
        current_conversation.setdefault("facts", [])
        current_conversation.setdefault("messages", [])


def get_current_timestamp_string():
    return datetime.now().replace(microsecond=0).isoformat()
