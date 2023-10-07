from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Context:
    def __init__(self, context_file):
        self.context_file = context_file
        self.load()

    def load(self):
        with open(self.context_file, "r") as file:
            self.data = yaml.load(file)

    def save(self):
        with open(self.context_file, "w") as file:
            yaml.dump(self.data, file)

    def add_message(self, role, message):
        self.current_conversation["messages"].append(
            {"role": role, "content": LiteralScalarString(message)}
        )

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

    @property
    def current_conversation(self):
        return self.data["conversations"][-1]

    @property
    def prompts(self):
        return self.data["prompts"]

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
    def current_conversation_size(self):
        return sum(len(item["content"]) for item in self.current_messages)

    @property
    def chat_prompt(self):
        return self.prompts["chat_prompt"]

    @property
    def reinforcement_chat_prompt(self):
        return self.prompts["reinforcement_chat_prompt"]

    @property
    def conversation_summarization_prompt(self):
        return self.prompts["conversation_summarization_prompt"]

    @property
    def memory_integration_prompt(self):
        return self.prompts["memory_integration_prompt"]
