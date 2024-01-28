import os
from datetime import datetime

from .conversation import Conversation
from .yaml_config import yaml


class Context:
    def __init__(self, filepath):
        self._filepath = filepath

    def load(self):
        with open(self._filepath, "r") as file:
            self._data = yaml.load(file)
        self.load_conversation()

    def save(self):
        with open(self._filepath, "w") as file:
            yaml.dump(self._data, file)
        self._conversation.save()

    def add_message(self, role, message, image_url=None):
        self._conversation.add_message(role, message, image_url)

    def trim_messages(self, n=None):
        self._conversation.trim_messages(n)

    def reset_conversation(self):
        self._conversation.reset()

    def new_conversation(self):
        self._data["conversation_name"] = self._new_conversation_name()
        self._load_conversation_by_name(self._data["conversation_name"])

    def _load_conversation_by_name(self, name):
        path = f"{self.dir}/conversations/{name}.yml"
        self._conversation = Conversation(path)
        self._conversation.load()

    def load_conversation(self):
        if "conversation_name" in self._data:
            self._load_conversation_by_name(self._data["conversation_name"])
        else:
            self.new_conversation()

    def increment_cost(self, new_cost):
        self._data["total_cost"] += new_cost
        self._conversation.increment_cost(new_cost)

    def add_conversation_fact(self, fact):
        self._conversation.add_fact(fact)

    @property
    def conversation_messages(self):
        return self._conversation.messages

    @property
    def conversation_facts(self):
        return self._conversation._facts

    @property
    def conversation_cost(self):
        return self._conversation.cost

    @property
    def dir(self):
        return os.path.dirname(self._filepath)

    @property
    def vars(self):
        return self._data["vars"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def _total_cost(self):
        return self._data["total_cost"]

    def _new_conversation_name(self):
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        return f"{self.name}-{timestamp}"
