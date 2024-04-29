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
        self._data["active_conversation"] = self._new_conversation_name()
        self._load_conversation_by_name(self._data["active_conversation"])

    def load_conversation(self):
        if "active_conversation" in self._data:
            self._load_conversation_by_name(self._data["active_conversation"])
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
    def model(self):
        model = self._data.get("model")
        if model:
            return model
        if self._is_openai():
            return "gpt-4-vision-preview"

    @property
    def instruction_template(self):
        return self._data.get("instruction_template")

    @property
    def api_provider(self):
        return self._data.get("api_provider") or "openai"

    @property
    def _total_cost(self):
        return self._data["total_cost"]

    def _new_conversation_name(self):
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        name = os.path.splitext(os.path.basename(self._filepath))[0]
        return f"{name}_{timestamp}"

    def _load_conversation_by_name(self, name):
        path = f"{self.dir}/conversations/{name}.yml"
        self._conversation = Conversation(path)
        self._conversation.load()

    def _is_openai(self):
        return self._data["provider"] == "openai" or self._data.get("provider") is None
