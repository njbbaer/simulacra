import os

from .conversation import Conversation
from .yaml_config import yaml


class Context:
    def __init__(self, filepath):
        self._filepath = filepath

    def load(self):
        with open(self._filepath, "r") as file:
            self._data = yaml.load(file)
        self._load_conversation()

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
        self._data["conversation_id"] = self._next_conversation_id()
        self._load_conversation()

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
    def conversations_dir(self):
        return f"{self.dir}/conversations"

    @property
    def vars(self):
        return self._data["vars"]

    @property
    def char_name(self):
        return self._data["char_name"]

    @property
    def api_provider(self):
        return self._data["api_provider"]

    @property
    def model(self):
        return self._data["model"]

    @property
    def conversation_id(self):
        return self._data.setdefault("conversation_id", self._next_conversation_id())

    @property
    def instruction_template(self):
        return self._data.get("instruction_template")

    def _load_conversation(self):
        path = f"{self.conversations_dir}/{self.char_name}_{self.conversation_id}.yml"
        self._conversation = Conversation(path)
        self._conversation.load()

    def _next_conversation_id(self):
        base_name = os.path.splitext(os.path.basename(self._filepath))[0]
        max_id = max(
            (
                int(os.path.splitext(file)[0].split("_")[1])
                for file in os.listdir(self.conversations_dir)
                if file.startswith(base_name + "_")
            ),
            default=0,
        )
        return max_id + 1
