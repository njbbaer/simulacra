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

    def add_message(self, role, message, photo_url=None):
        if photo_url:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": photo_url, "detail": "low"},
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
        new_messages = [] if n is None else self.current_messages[:-n]
        self.current_conversation["messages"] = new_messages

    def new_conversation(self, memory_chunks):
        self.data["conversations"].append(
            {
                "memory": [LiteralScalarString(x) for x in memory_chunks],
                "messages": [],
            }
        )

    def get_name(self, role):
        return self.data["names"][role]

    def add_cost(self, cost):
        self.data["total_cost"] = self.data.get("total_cost", 0) + cost

    @property
    def current_conversation(self):
        return self.data["conversations"][-1]

    @property
    def prompts(self):
        return self.data["prompts"]

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
    def current_memory_size(self):
        return len(self.current_memory)

    @property
    def chat_prompt(self):
        return self.prompts["chat_prompt"]

    @property
    def reinforcement_chat_prompt(self):
        return self.prompts.get("reinforcement_chat_prompt")

    @property
    def conversation_summarization_prompt(self):
        return self.prompts["conversation_summarization_prompt"]

    @property
    def memory_integration_prompt(self):
        return self.prompts["memory_integration_prompt"]

    @property
    def chat_model(self):
        return self.parameters.get("chat_model") or "gpt-4"

    def _initialize_conversation_data(self):
        self.data.setdefault("conversations", [{}])
        current_conversation = self.data["conversations"][-1]
        current_conversation.setdefault("memory", [])
        current_conversation.setdefault("messages", [])
