from src.yaml_config import yaml
from ruamel.yaml.scalarstring import LiteralScalarString
from contextlib import contextmanager


class Context:
    def __init__(self, context_file):
        self.context_file = context_file
        self.load()

    def load(self):
        with open(self.context_file, 'r') as file:
            self.data = yaml.load(file)

    def save(self):
        with open(self.context_file, 'w') as file:
            yaml.dump(self.data, file)

    def add_message(self, role, message):
        self.current_conversation['messages'].append({
            'role': role,
            'content': LiteralScalarString(message)
        })

    def clear_messages(self, n=None):
        new_messages = [] if n is None else self.current_messages[:-n]
        self.current_conversation['messages'] = new_messages

    def create_conversation(self, memory_state):
        self.data['conversations'].append({
            'memory_state': memory_state,
            'messages': [],
        })

    @property
    def current_conversation(self):
        return self.data['conversations'][-1]

    @property
    def current_messages(self):
        return self.current_conversation['messages']

    @property
    def current_memory_state(self):
        return self.current_conversation['memory_state']

    @property
    def chat_prompt(self):
        return LiteralScalarString(f'{self.data["chat_prompt"]}\n\n{self.current_memory_state}')

    @property
    def memory_integration_prompt(self):
        return self.data['memory_integration_prompt']
