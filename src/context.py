from src.yaml_config import yaml
from ruamel.yaml.scalarstring import LiteralScalarString


class Context:
    def __init__(self, context_file):
        self.context_file = context_file
        self.load()
        self.save()

    def save(self):
        with open(self.context_file, 'w') as file:
            yaml.dump(self.data, file)

    def load(self):
        with open(self.context_file, 'r') as file:
            self.data = yaml.load(file)

    def add_message(self, role, message):
        self.data.setdefault('messages', []).append({
            'role': role,
            'content': LiteralScalarString(message)
        })
        self.save()

    def set_memory(self, memory):
        self.data['current_memory'] = memory
        self.save()

    def clear_messages(self):
        if 'messages' in self.data:
            del self.data['messages']
        self.save()

    def delete_messages(self, n):
        self.data['messages'] = self.data['messages'][:-n]
        self.save()

    @property
    def chat_messages(self):
        return self.data.get('messages') or []

    @property
    def chat_prompt(self):
        return LiteralScalarString(self.data['chat_prompt'] + '\n\n' + self.current_memory)

    @property
    def memorizer_prompt(self):
        return self.data['memory_prompt']

    @property
    def current_memory(self):
        return self.data['current_memory']
