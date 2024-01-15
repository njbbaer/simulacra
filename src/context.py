from datetime import datetime

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Context:
    def __init__(self, context_file):
        self.context_file = context_file
        self.load()

    def load(self):
        with open(self.context_file, "r") as file:
            self.data = yaml.load(file)
        self._initialize_conversation_data()

    def save(self):
        with open(self.context_file, "w") as file:
            yaml.dump(self.data, file)

    def add_message(self, role, message, image_url=None):
        if image_url:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url, "detail": "low"},
                }
            ]
            if message:
                content.append({"type": "text", "text": LiteralScalarString(message)})
        else:
            content = LiteralScalarString(message)
        self.current_conversation["messages"].append({"role": role, "content": content})

    def append_memory(self, text):
        self.current_memory_chunks.append(text)

    def clear_messages(self, n=None):
        self.current_conversation["messages"] = self.current_messages[:-n]

    def reset_current_conversation(self):
        self.current_conversation["cost"] = 0
        self.current_conversation["messages"] = []

    def new_conversation(self, memory_chunks):
        self.data["conversations"].append(
            {
                "name": get_current_timestamp_string(),
                "memory": [LiteralScalarString(x) for x in memory_chunks],
                "cost": 0,
                "messages": [],
            }
        )

    def get_name(self, role):
        return self.data["names"][role]

    def add_cost(self, new_cost):
        self.data.setdefault("total_cost", 0)
        self.data["total_cost"] = self.total_cost + new_cost
        self.current_conversation["cost"] = self.current_conversation_cost + new_cost

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
    def current_memory(self):
        return "\n\n".join(self.current_conversation["memory"])

    @property
    def current_memory_chunks(self):
        return self.current_conversation["memory"]

    @property
    def chat_prompt(self):
        return self.vars["chat_prompt"]

    @property
    def reinforcement_chat_prompt(self):
        return self.vars.get("reinforcement_chat_prompt")

    @property
    def conversation_summarization_prompt(self):
        return self.vars["conversation_summarization_prompt"]

    @property
    def memory_integration_prompt(self):
        return self.vars["memory_integration_prompt"]

    @property
    def chat_model(self):
        return self.parameters.get("chat_model", "gpt-4")

    @property
    def total_cost(self):
        return self.data["total_cost"]

    @property
    def current_conversation_cost(self):
        return self.current_conversation.get("cost", 0)

    @property
    def enable_memory(self):
        return self.parameters.get("enable_memory", True)

    @property
    def image_prompts(self):
        return self.vars.get("image_prompts", [])

    def _initialize_conversation_data(self):
        self.data.setdefault("conversations", [{}])
        current_conversation = self.data["conversations"][-1]
        current_conversation.setdefault("name", get_current_timestamp_string())
        current_conversation.setdefault("cost", 0)
        current_conversation.setdefault("memory", [])
        current_conversation.setdefault("messages", [])


def get_current_timestamp_string():
    return datetime.now().replace(microsecond=0).isoformat()
